/*
 * Copyright (c) 2022-present Charles7c Authors. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package top.continew.admin.training.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.redisson.api.RBucket;
import org.redisson.api.RedissonClient;
import org.redisson.client.codec.StringCodec;
import top.continew.starter.core.exception.BusinessException;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 活体挑战的一次性消费、上下文与采集帧绑定测试。
 * @author 工程实训小组
 * @since 4.2.0
 */
class FaceLivenessServiceTest {

    private final ObjectMapper mapper = new ObjectMapper();
    private final Map<String, String> values = new ConcurrentHashMap<>();
    private FaceRecognitionService recognition;
    private FaceLivenessService service;

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        RedissonClient redis = mock(RedissonClient.class);
        recognition = mock(FaceRecognitionService.class);
        when(redis.getBucket(anyString(), eq(StringCodec.INSTANCE))).thenAnswer(call -> {
            String key = call.getArgument(0);
            RBucket<String> bucket = mock(RBucket.class);
            when(bucket.get()).thenAnswer(ignored -> values.get(key));
            when(bucket.getAndDelete()).thenAnswer(ignored -> values.remove(key));
            doAnswer(set -> {
                values.put(key, set.getArgument(0));
                return null;
            })
                .when(bucket).set(anyString(), any(Duration.class));
            return bucket;
        });
        when(recognition.liveness(any(), eq(0L)))
            .thenReturn(mapper.createObjectNode().put("passed", true));
        service = new FaceLivenessService(redis, mapper, recognition);
    }

    @Test
    void streamingProofRequiresCompletedRecognitionAndCannotReplay() {
        when(recognition.session(any(), eq(0L)))
            .thenReturn(mapper.createObjectNode().put("sessionId", "remote"))
            .thenReturn(mapper.createObjectNode().put("done", false).put("action", "turn"))
            .thenReturn(mapper.createObjectNode().put("done", true).put("account", "123"));
        String id = service.startSession("scope", 0L, 123L).path("sessionId").asText();
        assertEquals(false, service.frame(id, "frame1", "scope", 0L).has("livenessToken"));
        ObjectNode result = service.frame(id, "frame2", "scope", 0L);
        assertEquals(false, result.has("account"));
        String token = result.path("livenessToken").asText();
        service.consume(token, "frame2", "scope");
        assertThrows(BusinessException.class, () -> service.consume(token, "frame2", "scope"));
        assertThrows(BusinessException.class, () -> service.frame(id, "frame2", "scope", 0L));
    }

    @Test
    void streamingFailureDoesNotIssueProof() {
        when(recognition.session(any(), eq(0L)))
            .thenReturn(mapper.createObjectNode().put("sessionId", "remote"))
            .thenReturn(mapper.createObjectNode().put("done", true).putNull("account"));
        String id = service.startSession("scope", 0L, 123L).path("sessionId").asText();
        assertEquals(false, service.frame(id, "frame", "scope", 0L).has("livenessToken"));
        assertThrows(BusinessException.class, () -> service.frame(id, "frame", "scope", 0L));
    }

    @Test
    void streamingContextChangeIsRejected() {
        when(recognition.session(any(), eq(0L)))
            .thenReturn(mapper.createObjectNode().put("sessionId", "remote"));
        String id = service.startSession("scope", 0L, 123L).path("sessionId").asText();
        assertThrows(BusinessException.class, () -> service.frame(id, "frame", "other", 0L));
        verify(recognition).session(any(), eq(0L));
    }

    private String challenge(String scope) throws Exception {
        var challenge = service.start(scope);
        assertEquals(2, challenge.actions().size());
        assertEquals(2, challenge.actions().stream().distinct().count());
        String key = "training:face:liveness:challenge:" + challenge.challengeId();
        ObjectNode state = (ObjectNode) mapper.readTree(values.get(key));
        state.put("issuedAt", System.currentTimeMillis() - 8000);
        values.put(key, state.toString());
        return challenge.challengeId();
    }

    @Test
    void proofIsSingleUseAndBoundToFinalFrame() throws Exception {
        String id = challenge("scope");
        var proof = service.verify(id, List.of(List.of("first"), List.of("final")), "scope", 0L);
        service.consume(proof.livenessToken(), "final", "scope");
        assertThrows(BusinessException.class,
            () -> service.consume(proof.livenessToken(), "final", "scope"));
        assertThrows(BusinessException.class, () -> service.verify(id, List.of(), "scope", 0L));
        verify(recognition).liveness(any(), eq(0L));
    }

    @Test
    void replacingFrameBurnsProof() throws Exception {
        var proof = service.verify(challenge("scope"), List.of(List.of("first"), List.of("final")),
            "scope", 0L);
        assertThrows(BusinessException.class,
            () -> service.consume(proof.livenessToken(), "different", "scope"));
        assertThrows(BusinessException.class,
            () -> service.consume(proof.livenessToken(), "final", "scope"));
    }

    @Test
    void changedScopeIsRejectedBeforeRecognition() throws Exception {
        String id = challenge("original");
        assertThrows(BusinessException.class,
            () -> service.verify(id, List.of(), "other-account", 0L));
        verify(recognition, never()).liveness(any(), any());
    }

    @Test
    void prematureOrExpiredChallengeCannotPass() throws Exception {
        String early = service.start("scope").challengeId();
        assertThrows(BusinessException.class, () -> service.verify(early, List.of(), "scope", 0L));
        String expired = challenge("scope");
        values.remove("training:face:liveness:challenge:" + expired);
        assertThrows(BusinessException.class,
            () -> service.verify(expired, List.of(), "scope", 0L));
        verify(recognition, never()).liveness(any(), any());
    }

    @Test
    void missingProofAndFailedLivenessCannotPass() throws Exception {
        assertThrows(BusinessException.class, () -> service.consume(null, "image", "scope"));
        when(recognition.liveness(any(), eq(0L)))
            .thenReturn(mapper.createObjectNode().put("passed", false));
        String id = challenge("scope");
        assertThrows(BusinessException.class, () -> service.verify(id, List.of(), "scope", 0L));
        assertEquals(0, values.size());
    }

    @Test
    void scopeSeparatesTenantAccountClientAndMode() {
        String original = service.scope(0L, "client", false, "000001", "127.0.0.1");
        assertEquals(5, List.of(original, service.scope(1L, "client", false, "000001", "127.0.0.1"),
            service.scope(0L, "client", false, "000002", "127.0.0.1"),
            service.scope(0L, "other", false, "000001", "127.0.0.1"),
            service.scope(0L, "client", true, null, "127.0.0.1")).stream().distinct().count());
    }
}
