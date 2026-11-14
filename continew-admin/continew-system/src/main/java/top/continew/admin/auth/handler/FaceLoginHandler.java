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

package top.continew.admin.auth.handler;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import top.continew.admin.auth.AbstractLoginHandler;
import top.continew.admin.auth.enums.AuthTypeEnum;
import top.continew.admin.auth.model.req.FaceLoginReq;
import top.continew.admin.auth.model.resp.LoginResp;
import top.continew.admin.system.model.entity.user.UserDO;
import top.continew.admin.system.model.resp.ClientResp;
import top.continew.admin.training.service.FaceRecognitionService;
import top.continew.starter.core.exception.BusinessException;
import top.continew.starter.extension.tenant.context.TenantContextHolder;
import top.continew.starter.ratelimiter.annotation.RateLimiter;
import top.continew.starter.ratelimiter.enums.LimitType;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.concurrent.TimeUnit;

/**
 * 当前租户内的一对一验证和已授权账号的一对多识别。
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@Component
@RequiredArgsConstructor
public class FaceLoginHandler extends AbstractLoginHandler<FaceLoginReq> {

    private final FaceRecognitionService recognition;

    @Override
    @RateLimiter(name = "training:face:login", rate = 12, interval = 1, unit = TimeUnit.MINUTES,
        type = LimitType.IP, message = "刷脸尝试过于频繁，请稍后再试")
    public LoginResp login(FaceLoginReq req, ClientResp client, HttpServletRequest request,
        HttpServletResponse response) {
        Long tenant = TenantContextHolder.isTenantEnabled() ? TenantContextHolder.getTenantId()
            : Long.valueOf(0L);
        if (req.isIdentify()) {
            if (req.getUsername() != null && !req.getUsername().isBlank()) {
                throw new BusinessException("免输账号模式无需指定用户名");
            }
            long id =
                recognition.run("identify", tenant, 0, 0, req.getImage()).path("userId").asLong(0);
            UserDO matched = id > 0 ? userService.getById(id) : null;
            if (matched == null) {
                throw new BusinessException("验证未通过，可重试或使用密码登录");
            }
            return authenticate(matched, client, request, response);
        }
        if (req.getUsername() == null || req.getUsername().isBlank()) {
            throw new BusinessException("请输入账号或选择免输账号模式");
        }
        UserDO user = userService.getByUsername(req.getUsername());
        if (user == null || !recognition.run("verify", tenant, user.getId(), 0, req.getImage())
            .path("matched").asBoolean(false)) {
            throw new BusinessException("验证未通过，可重试或使用密码登录");
        }
        return authenticate(user, client, request, response);
    }

    @Override
    public AuthTypeEnum getAuthType() {
        return AuthTypeEnum.FACE;
    }
}
