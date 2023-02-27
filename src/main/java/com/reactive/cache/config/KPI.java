package com.reactive.cache.config;

import com.reactive.cache.enums.KPITypes;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.apache.commons.lang3.time.StopWatch;
import org.springframework.stereotype.Component;

import java.util.function.Supplier;

@Component
public class KPI {

    private static final Logger logger = LoggerFactory.getLogger(KPI.class);

    public <T> T measure(KPITypes kpiTypes, String action, Supplier<T> supplier) {
        StopWatch stopWatch = new StopWatch();
        stopWatch.start();
        T result = supplier.get();
        stopWatch.stop();
        logger.info("{}: action - {}, nano seconds - {}", kpiTypes, action, stopWatch.getNanoTime());

        return result;
    }

}
