package com.example.shortener.service;

import java.net.URI;
import com.example.shortener.vo.Analytics;
import com.example.shortener.vo.CreateRequest;
import com.example.shortener.vo.CreateResponse;

public interface UrlService {
    CreateResponse create(CreateRequest request, String baseUrl);

    URI redirect(String code);

    Analytics analytics(String code);
}