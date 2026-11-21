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

import cn.hutool.crypto.digest.DigestUtil;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.RequiredArgsConstructor;
import org.redisson.api.RBucket;
import org.redisson.api.RedissonClient;
import org.redisson.client.codec.StringCodec;
import org.springframework.stereotype.Service;
import top.continew.starter.core.exception.BusinessException;

import java.security.SecureRandom;
import java.time.Duration;
import java.util.List;
import java.util.UUID;

/**
 * 服务端随机活体挑战及一次性登录凭证，不保存原始采集画面。
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@Service
@RequiredArgsConstructor
public class FaceLivenessService {

    private static final SecureRandom RANDOM = new SecureRandom();
    private final RedissonClient redis;
    private final ObjectMapper mapper;
    private final FaceRecognitionService recognition;

    public record Challenge(String challengeId, List<String> actions, int expiresIn) {
    }

    public record Proof(String livenessToken, int expiresIn) {
    }

    /**
     * 生成绑定登录上下文的短期随机挑战。
     * @param scope 登录上下文摘要
     * @return 挑战
     * @since 4.2.0
     */
    public Challenge start(String scope) {
        String id = UUID.randomUUID().toString();
        List<String> actions =
            RANDOM.nextBoolean() ? List.of("blink", "mouth") : List.of("mouth", "blink");
        ObjectNode state = mapper.createObjectNode().put("scope", scope).put("issuedAt",
            System.currentTimeMillis());
        state.set("actions", mapper.valueToTree(actions));
        bucket("challenge", id).set(state.toString(), Duration.ofSeconds(60));
        return new Challenge(id, actions, 60);
    }

    /**
     * 消耗挑战，在后端验证连续画面后签发仅绑定末帧的凭证。
     * @param id 挑战编号
     * @param batches 按步骤采集的画面
     * @param scope 登录上下文摘要
     * @param tenant 当前租户
     * @return 一次性凭证
     * @since 4.2.0
     */
    public Proof verify(String id, List<List<String>> batches, String scope, Long tenant) {
        JsonNode state = take("challenge", id, scope);
        long elapsed = System.currentTimeMillis() - state.path("issuedAt").asLong();
        if (elapsed < 6000 || elapsed > 60000) {
            throw new BusinessException("活体采集时长无效，请重新开启摄像头");
        }
        ObjectNode req = mapper.createObjectNode();
        req.set("actions", state.path("actions"));
        req.set("batches", mapper.valueToTree(batches));
        if (!recognition.liveness(req, tenant).path("passed").asBoolean(false)) {
            throw new BusinessException("活体验证未通过，请重新开启摄像头");
        }
        List<String> last = batches.get(batches.size() - 1);
        String proof = UUID.randomUUID().toString();
        ObjectNode ticket = mapper.createObjectNode().put("scope", scope)
            .put("imageHash", DigestUtil.sha256Hex(last.get(last.size() - 1)));
        bucket("proof", proof).set(ticket.toString(), Duration.ofSeconds(20));
        return new Proof(proof, 20);
    }

    /**
     * 登录必须消费活体凭证，拒绝重复使用或替换人脸画面。
     * @param token 一次性凭证
     * @param image 人脸匹配画面
     * @param scope 登录上下文摘要
     * @since 4.2.0
     */
    public void consume(String token, String image, String scope) {
        JsonNode ticket = take("proof", token, scope);
        if (!ticket.path("imageHash").asText().equals(DigestUtil.sha256Hex(image))) {
            throw new BusinessException("活体画面不一致，请重新开启摄像头");
        }
    }

    /**
     * 绑定租户、客户端、模式、账号及连接来源。
     * @param tenant 当前租户
     * @param client 客户端编号
     * @param identify 是否免输账号
     * @param username 用户名
     * @param address 连接来源
     * @return 摘要
     * @since 4.2.0
     */
    public String scope(Long tenant, String client, boolean identify, String username,
        String address) {
        if (tenant == null || (!identify && (username == null || username.isBlank()))
            || (identify && username != null && !username.isBlank())) {
            throw new BusinessException("请选择识别方式并检查账号或租户");
        }
        return DigestUtil.sha256Hex(mapper.createArrayNode().add(tenant).add(client).add(identify)
            .add(username == null ? "" : username.trim()).add(address).toString());
    }

    private JsonNode take(String kind, String id, String scope) {
        if (id == null || !id.matches("[0-9a-f-]{36}")) {
            throw new BusinessException("请先完成活体验证");
        }
        String value = bucket(kind, id).getAndDelete();
        if (value == null) {
            throw new BusinessException("活体凭证已失效或已使用，请重新开启摄像头");
        }
        try {
            JsonNode state = mapper.readTree(value);
            if (!state.path("scope").asText().equals(scope)) {
                throw new BusinessException("登录信息已变化，请重新开启摄像头");
            }
            return state;
        } catch (java.io.IOException e) {
            throw new BusinessException("活体凭证无效，请重新开启摄像头");
        }
    }

    private RBucket<String> bucket(String kind, String id) {
        return redis.getBucket("training:face:liveness:" + kind + ":" + id, StringCodec.INSTANCE);
    }
}
