package com.example.shortener.vo;

import java.time.Instant;

public record Analytics(String code, long clickCount, Instant createdAt, Instant expiresAt, boolean expired) {
}
