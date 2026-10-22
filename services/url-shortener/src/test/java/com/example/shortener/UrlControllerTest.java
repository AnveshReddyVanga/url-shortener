package com.example.shortener;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.net.URI;
import java.time.Instant;

import com.example.shortener.controller.UrlController;
import com.example.shortener.service.UrlService;
import com.example.shortener.vo.Analytics;
import com.example.shortener.vo.CreateRequest;
import com.example.shortener.vo.CreateResponse;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(UrlController.class)
@TestPropertySource(properties = "app.shortener.base-url=https://short.test:8443")
class UrlControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private UrlService urlService;

    @Test
    void createReturnsCreatedResponseAndPassesRequestToService() throws Exception {
        Instant createdAt = Instant.parse("2026-01-02T03:04:05Z");
        CreateResponse response = new CreateResponse(
                "abc1234",
                "https://short.test:8443/abc1234",
                "https://example.test/path",
                createdAt,
                null);
        given(urlService.create(any(CreateRequest.class), eq("https://short.test:8443")))
                .willReturn(response);

        mockMvc.perform(post("/api/urls")
                        .with(request -> {
                            request.setScheme("https");
                            request.setServerName("attacker.example");
                            request.setServerPort(8443);
                            request.setSecure(true);
                            return request;
                        })
                        .contentType(MediaType.APPLICATION_JSON_VALUE)
                        .content("""
                {"url":"https://example.test/path","customCode":"abc1234"}
                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.code").value("abc1234"))
                .andExpect(jsonPath("$.shortUrl")
                        .value("https://short.test:8443/abc1234"))
                .andExpect(jsonPath("$.originalUrl")
                        .value("https://example.test/path"))
                .andExpect(jsonPath("$.createdAt").value(createdAt.toString()));

        then(urlService).should().create(any(CreateRequest.class), eq("https://short.test:8443"));
        verifyNoMoreInteractions(urlService);
    }

    @Test
    void createRejectsBlankUrlWithoutCallingService() throws Exception {
        mockMvc.perform(post("/api/urls")
                        .contentType(MediaType.APPLICATION_JSON_VALUE)
                        .content("""
                {"url":"   "}
                """))
                .andExpect(status().isBadRequest());

        then(urlService).should(never()).create(any(CreateRequest.class), any(String.class));
        verifyNoMoreInteractions(urlService);
    }

    @Test
    void redirectReturnsFoundWithLocationHeader() throws Exception {
        given(urlService.redirect("abc1234"))
                .willReturn(URI.create("https://example.test/path"));

        mockMvc.perform(get("/abc1234"))
                .andExpect(status().isFound())
                .andExpect(header().string("Location", "https://example.test/path"));

        then(urlService).should().redirect("abc1234");
        verifyNoMoreInteractions(urlService);
    }

    @Test
    void analyticsReturnsServiceResult() throws Exception {
        Instant createdAt = Instant.parse("2026-01-02T03:04:05Z");
        given(urlService.analytics("abc1234"))
                .willReturn(new Analytics("abc1234", 7, createdAt, null, false));

        mockMvc.perform(get("/api/urls/abc1234/analytics"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("abc1234"))
                .andExpect(jsonPath("$.clickCount").value(7))
                .andExpect(jsonPath("$.createdAt").value(createdAt.toString()))
                .andExpect(jsonPath("$.expired").value(false));

        then(urlService).should().analytics("abc1234");
        verifyNoMoreInteractions(urlService);
    }
}
