package com.example.shortener.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import java.net.URI;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import com.example.shortener.service.UrlService;
import com.example.shortener.vo.Analytics;
import com.example.shortener.vo.CreateRequest;
import com.example.shortener.vo.CreateResponse;

@RestController
@RequiredArgsConstructor
public class UrlController {
    private final UrlService urlService;

    @Value("${app.shortener.base-url}")
    private String baseUrl;

    @PostMapping("/api/urls")
    public ResponseEntity<CreateResponse> create(@Valid @RequestBody CreateRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(urlService.create(req, baseUrl));
    }

    @GetMapping("/{code:[A-Za-z0-9_-]{3,32}}")
    public ResponseEntity<Void> redirect(@PathVariable String code) {
        URI location = urlService.redirect(code);
        return ResponseEntity.status(HttpStatus.FOUND)
                .header(HttpHeaders.LOCATION, location.toString())
                .build();
    }

    @GetMapping("/api/urls/{code}/analytics")
    public Analytics analytics(@PathVariable String code) {
        return urlService.analytics(code);
    }
}