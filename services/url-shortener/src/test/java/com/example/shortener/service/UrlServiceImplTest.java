package com.example.shortener.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;

import java.net.URI;
import java.time.Instant;
import java.util.Optional;

import com.example.shortener.entity.ShortUrl;
import com.example.shortener.repo.ShortUrlRepository;
import com.example.shortener.vo.Analytics;
import com.example.shortener.vo.CreateRequest;
import com.example.shortener.vo.CreateResponse;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@ExtendWith(MockitoExtension.class)
class UrlServiceImplTest {
    @Mock
    private ShortUrlRepository repo;

    @InjectMocks
    private UrlServiceImpl service;

    @Test
    void createSavesCustomAliasAndReturnsShortUrlResponse() {
        Instant expiresAt = Instant.parse("2027-01-01T00:00:00Z");
        Instant createdAt = Instant.parse("2026-01-02T03:04:05Z");
        given(repo.existsByCode("custom_1")).willReturn(false);
        
        given(repo.saveAndFlush(any(ShortUrl.class))).willReturn(new ShortUrl(
                null, "https://example.test/path", "custom_1", createdAt, expiresAt, 0L));

        CreateResponse response = service.create(
                new CreateRequest(" https://example.test/path ", "custom_1", expiresAt),
                "https://short.test");

        assertEquals("custom_1", response.code());
        assertEquals("https://short.test/custom_1", response.shortUrl());
        assertEquals("https://example.test/path", response.originalUrl());
        assertEquals(createdAt, response.createdAt());
        assertEquals(expiresAt, response.expiresAt());
        verify(repo).existsByCode("custom_1");
        verify(repo).saveAndFlush(any(ShortUrl.class));
        verifyNoMoreInteractions(repo);
    }

    @Test
    void createGeneratesCodeWhenCustomCodeIsMissing() {
        given(repo.saveAndFlush(any(ShortUrl.class))).willAnswer(invocation -> invocation.getArgument(0));

        CreateResponse response = service.create(
                new CreateRequest("https://example.test", null, null),
                "https://short.test");

        assertTrue(response.code().matches("[A-Za-z0-9]{7}"));
        assertEquals("https://short.test/" + response.code(), response.shortUrl());
        verify(repo).saveAndFlush(any(ShortUrl.class));
    }

    @Test
    void createRejectsNonHttpScheme() {
        ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                () -> service.create(new CreateRequest("ftp://example.test", null, null),
                        "https://short.test"));

        assertEquals(HttpStatus.BAD_REQUEST, exception.getStatusCode());
        verifyNoMoreInteractions(repo);
    }

    @Test
    void createRejectsDuplicateCustomCode() {
        given(repo.existsByCode("taken")).willReturn(true);

        ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                () -> service.create(new CreateRequest("https://example.test", "taken", null),
                        "https://short.test"));

        assertEquals(HttpStatus.CONFLICT, exception.getStatusCode());
        verify(repo, never()).saveAndFlush(any(ShortUrl.class));
        verifyNoMoreInteractions(repo);
    }

    @Test
    void createRejectsExpirationThatIsNotInTheFuture() {
        Instant expiredAt = Instant.now().minusSeconds(1);

        ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                () -> service.create(new CreateRequest("https://example.test", null, expiredAt),
                        "https://short.test"));

        assertEquals(HttpStatus.BAD_REQUEST, exception.getStatusCode());
        verifyNoMoreInteractions(repo);
    }

    @Test
    void createRetriesWhenGeneratedCodeCollidesAtDatabaseInsert() {
        given(repo.saveAndFlush(any(ShortUrl.class)))
                .willThrow(new DataIntegrityViolationException("unique code collision"))
                .willAnswer(invocation -> invocation.getArgument(0));

        CreateResponse response = service.create(
                new CreateRequest("https://example.test", null, null),
                "https://short.test/");

        assertTrue(response.code().matches("[A-Za-z0-9]{7}"));
        assertEquals("https://short.test/" + response.code(), response.shortUrl());
        verify(repo, org.mockito.Mockito.times(2)).saveAndFlush(any(ShortUrl.class));
    }

    @Test
    void createReturnsConflictWhenCustomAliasLosesConcurrentInsertRace() {
        given(repo.existsByCode("taken")).willReturn(false);
        given(repo.saveAndFlush(any(ShortUrl.class)))
                .willThrow(new DataIntegrityViolationException("unique code collision"));

        ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                () -> service.create(new CreateRequest("https://example.test", "taken", null),
                        "https://short.test"));

        assertEquals(HttpStatus.CONFLICT, exception.getStatusCode());
        verify(repo).existsByCode("taken");
        verify(repo).saveAndFlush(any(ShortUrl.class));
    }

    @Test
    void redirectIncrementsClicksAndReturnsOriginalUri() {
        ShortUrl shortUrl = new ShortUrl(
                null, "https://example.test/path", "abc1234", Instant.now(), null, 0L);
        given(repo.findByCode("abc1234")).willReturn(Optional.of(shortUrl));

        given(repo.incrementClickCountByCode("abc1234")).willReturn(1);

        URI location = service.redirect("abc1234");

        assertEquals(URI.create("https://example.test/path"), location);
        // Counter updates are executed atomically in the database, not on this stale entity.
        assertEquals(0, shortUrl.getClickCount());
        verify(repo).findByCode("abc1234");
        verify(repo).incrementClickCountByCode("abc1234");
        verifyNoMoreInteractions(repo);
    }

    @Test
    void redirectRejectsExpiredAlias() {
        ShortUrl shortUrl = new ShortUrl(null, "https://example.test/path", "abc1234",
                Instant.now(), Instant.now().minusSeconds(1), 0L);
        given(repo.findByCode("abc1234")).willReturn(Optional.of(shortUrl));

        ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                () -> service.redirect("abc1234"));

        assertEquals(HttpStatus.GONE, exception.getStatusCode());
        assertEquals(0, shortUrl.getClickCount());
        verify(repo).findByCode("abc1234");
        verifyNoMoreInteractions(repo);
    }

    @Test
    void analyticsReturnsClickCountAndExpiryState() {
        Instant createdAt = Instant.parse("2026-01-02T03:04:05Z");
        ShortUrl shortUrl = new ShortUrl(
                null, "https://example.test/path", "abc1234", createdAt, null, 4L);
        given(repo.findByCode("abc1234")).willReturn(Optional.of(shortUrl));

        Analytics analytics = service.analytics("abc1234");

        assertEquals("abc1234", analytics.code());
        assertEquals(4, analytics.clickCount());
        assertEquals(createdAt, analytics.createdAt());
        assertFalse(analytics.expired());
        verify(repo).findByCode("abc1234");
        verifyNoMoreInteractions(repo);
    }
}
