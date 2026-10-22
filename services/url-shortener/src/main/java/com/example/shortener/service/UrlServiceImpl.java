package com.example.shortener.service;

import java.net.URI;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import com.example.shortener.entity.ShortUrl;
import com.example.shortener.repo.ShortUrlRepository;
import com.example.shortener.vo.Analytics;
import com.example.shortener.vo.CreateRequest;
import com.example.shortener.vo.CreateResponse;

@Service
@RequiredArgsConstructor
public class UrlServiceImpl implements UrlService {
    private final ShortUrlRepository repo;

    private static final String ALPHABET =
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    private static final SecureRandom RANDOM = new SecureRandom();

    @Override
    public CreateResponse create(CreateRequest req, String baseUrl) {
        URI uri;
        String originalUrl = req.url().trim();
        try {
            uri = URI.create(originalUrl);
        } catch (IllegalArgumentException e) {
            throw badUrl();
        }

        boolean validHttpUrl = Optional.ofNullable(uri.getScheme())
            .filter(scheme -> "http".equalsIgnoreCase(scheme)
                || "https".equalsIgnoreCase(scheme))
            .flatMap(scheme -> Optional.ofNullable(uri.getHost()))
            .filter(host -> !host.isBlank())
            .isPresent();
        if (!validHttpUrl) {
            throw badUrl();
        }

        Optional.ofNullable(req.expiresAt())
            .filter(expiresAt -> !expiresAt.isAfter(Instant.now()))
            .ifPresent(expiresAt -> {
                throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "expiresAt must be in the future");
            });

        String customCode = Optional.ofNullable(req.customCode())
                .map(String::trim)
                .filter(value -> !value.isEmpty())
                .orElse(null);

        if (customCode != null) {
            if (!customCode.matches("[A-Za-z0-9_-]{3,32}")) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST,
                        "customCode must be 3-32 letters, digits, _ or -");
            }
            if (repo.existsByCode(customCode)) {
                throw new ResponseStatusException(
                        HttpStatus.CONFLICT, "customCode already exists");
            }
            return saveUrl(originalUrl, customCode, req.expiresAt(), baseUrl, true);
        }

        // The database unique constraint is the final authority. Retry collisions
        // rather than relying on a racy existsByCode() check.
        for (int attempt = 0; attempt < 10; attempt++) {
            try {
                return saveUrl(originalUrl, generateCode(), req.expiresAt(), baseUrl, false);
            } catch (DataIntegrityViolationException collision) {
                // A generated code collided with another request; try a new code.
            }
        }
        throw new ResponseStatusException(
                HttpStatus.SERVICE_UNAVAILABLE, "Could not allocate unique code");
    }

    private CreateResponse saveUrl(
            String originalUrl, String code, Instant expiresAt, String baseUrl, boolean customCode) {
        ShortUrl entity = ShortUrl.builder()
                .originalUrl(originalUrl)
                .code(code)
                .expiresAt(expiresAt)
                .build();
        try {
            ShortUrl savedUrl = repo.saveAndFlush(entity);
            return new CreateResponse(
                    savedUrl.getCode(),
                    baseUrl.replaceAll("/+$", "") + "/" + savedUrl.getCode(),
                    savedUrl.getOriginalUrl(),
                    savedUrl.getCreatedAt(),
                    savedUrl.getExpiresAt());
        } catch (DataIntegrityViolationException exception) {
            if (customCode) {
                throw new ResponseStatusException(
                        HttpStatus.CONFLICT, "customCode already exists", exception);
            }
            throw exception;
        }
    }

    @Override
    @Transactional
    public URI redirect(String code) {
        ShortUrl item = repo.findByCode(code)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND, "Short URL not found"));

        if (item.isExpired(Instant.now())) {
            throw new ResponseStatusException(
                    HttpStatus.GONE, "Short URL has expired");
        }

        int updated = repo.incrementClickCountByCode(code);
        if (updated == 0) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND, "Short URL not found");
        }
        return URI.create(item.getOriginalUrl());
    }

    @Override
    @Transactional(readOnly = true)
    public Analytics analytics(String code) {
        ShortUrl item = repo.findByCode(code)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND, "Short URL not found"));

        return new Analytics(
                code,
                item.getClickCount(),
                item.getCreatedAt(),
                item.getExpiresAt(),
                item.isExpired(Instant.now()));
    }

    private ResponseStatusException badUrl() {
        return new ResponseStatusException(
                HttpStatus.BAD_REQUEST,
                "url must be a valid absolute http/https URL");
    }

    private String generateCode() {
        StringBuilder code = new StringBuilder(7);
        for (int i = 0; i < 7; i++) {
            code.append(ALPHABET.charAt(RANDOM.nextInt(ALPHABET.length())));
        }
        return code.toString();
    }
}