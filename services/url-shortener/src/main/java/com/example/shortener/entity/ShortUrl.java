package com.example.shortener.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import java.time.Instant;

@Entity
@Getter
@Setter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "short_urls", indexes = @Index(name = "idx_short_code", columnList = "code", unique = true))
public class ShortUrl {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @NotBlank
    @Size(max = 2048)
    @Column(nullable = false, length = 2048)
    private String originalUrl;

    @NotBlank
    @Pattern(regexp = "[A-Za-z0-9_-]{3,32}")
    @Column(nullable = false, unique = true, length = 32)
    private String code;
    
    @NotNull
    @Column(nullable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();

    private Instant expiresAt;

    @Column(nullable = false)
    @Builder.Default
    private long clickCount = 0;

    public boolean isExpired(Instant now) {
        return expiresAt != null && !expiresAt.isAfter(now);
    }

}