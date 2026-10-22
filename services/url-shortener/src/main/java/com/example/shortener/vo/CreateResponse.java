package com.example.shortener.vo;

import java.time.Instant;

public record CreateResponse(String code, String shortUrl, String originalUrl, Instant createdAt,
        Instant expiresAt) {
}
