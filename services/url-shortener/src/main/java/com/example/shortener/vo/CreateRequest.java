package com.example.shortener.vo;

import java.time.Instant;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreateRequest(@NotBlank @Size(max = 2048) String url, @Size(max = 32) String customCode,
        Instant expiresAt) {
}
