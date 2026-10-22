package com.example.shortener.repo;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import com.example.shortener.entity.ShortUrl;
import java.util.Optional;

public interface ShortUrlRepository extends JpaRepository<ShortUrl, Long> {
    Optional<ShortUrl> findByCode(String code);

    boolean existsByCode(String code);

    /** Atomically increments the counter in the database, avoiding lost updates under concurrency. */
    @Modifying(flushAutomatically = true, clearAutomatically = true)
    @Query("update ShortUrl s set s.clickCount = s.clickCount + 1 where s.code = :code")
    int incrementClickCountByCode(@Param("code") String code);
}