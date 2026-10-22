package com.example.shortener;

import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;

import com.example.shortener.vo.Analytics;
import com.example.shortener.controller.UrlController;
import com.example.shortener.service.UrlService;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(UrlController.class)
@TestPropertySource(properties = "app.shortener.base-url=https://short.test:8443")
class UrlControllerAnalyticsTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private UrlService urlService;

    @Test
    void analyticsReturnsCorrectJsonResponse() throws Exception {
        Instant createdAt = Instant.parse("2026-01-02T03:04:05Z");
        Instant expiresAt = Instant.parse("2027-01-01T00:00:00Z");
        Analytics analytics = new Analytics("testcode", 42, createdAt, expiresAt, false);

        given(urlService.analytics("testcode")).willReturn(analytics);

        mockMvc.perform(get("/api/urls/testcode/analytics")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("testcode"))
                .andExpect(jsonPath("$.clickCount").value(42))
                .andExpect(jsonPath("$.createdAt").value(createdAt.toString()))
                .andExpect(jsonPath("$.expiresAt").value(expiresAt.toString()))
                .andExpect(jsonPath("$.expired").value(false));

        then(urlService).should().analytics("testcode");
        verifyNoMoreInteractions(urlService);
    }

}