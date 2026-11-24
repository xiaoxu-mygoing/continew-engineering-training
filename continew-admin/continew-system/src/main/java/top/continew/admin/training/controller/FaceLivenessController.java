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

package top.continew.admin.training.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import top.continew.admin.system.model.entity.user.UserDO;
import top.continew.admin.system.service.UserService;
import top.continew.admin.training.service.FaceLivenessService;
import top.continew.starter.core.exception.BusinessException;
import top.continew.starter.extension.tenant.context.TenantContextHolder;
import top.continew.starter.log.annotation.Log;
import top.continew.starter.ratelimiter.annotation.RateLimiter;
import top.continew.starter.ratelimiter.enums.LimitType;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 登录前活体挑战，采集帧和凭证不写入操作日志。
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@SaIgnore
@Log(ignore = true)
@RestController
@RequiredArgsConstructor
@RequestMapping("/auth/face/liveness")
public class FaceLivenessController {

    private final FaceLivenessService liveness;
    private final UserService userService;

    public record FrameRequest(@NotBlank @Size(max = 36) String sessionId,
        @NotNull @Valid Context context, @NotBlank @Size(max = 450000) String image) {
    }

    /**
     * 开启新版逐帧识别。
     * @param context 登录信息
     * @param request 请求
     * @return 会话编号
     * @since 4.2.0
     */
    @PostMapping("/session")
    @RateLimiter(name = "training:face:stream:start", rate = 8, interval = 1,
        unit = TimeUnit.MINUTES, type = LimitType.IP, message = "尝试过于频繁，请稍后重试")
    public ObjectNode session(@RequestBody @Valid Context context, HttpServletRequest request) {
        String contextScope = scope(context, request);
        long id = 0;
        if (!context.identify()) {
            UserDO user = userService.getByUsername(context.username().trim());
            if (user == null) {
                throw new BusinessException("请检查账号及人脸绑定状态");
            }
            id = user.getId();
        }
        return liveness.startSession(contextScope, tenant(), id);
    }

    /**
     * 逐帧判断动作与身份。
     * @param input 当前帧
     * @param request 请求
     * @param response 响应
     * @return 状态提示
     * @since 4.2.0
     */
    @PostMapping("/frame")
    @RateLimiter(name = "training:face:stream:frame", rate = 360, interval = 1,
        unit = TimeUnit.MINUTES, type = LimitType.IP, message = "检测过于频繁，请稍后重试")
    public ObjectNode frame(@RequestBody @Valid FrameRequest input, HttpServletRequest request,
        HttpServletResponse response) {
        response.setHeader("Cache-Control", "no-store");
        return liveness.frame(input.sessionId(), input.image(), scope(input.context(), request),
            tenant());
    }

    public record Context(@NotBlank @Size(max = 64) String clientId, boolean identify,
        @Size(max = 64) String username) {
    }

    public record VerifyRequest(@NotBlank @Size(max = 36) String challengeId,
        @NotNull @Valid Context context,
        @NotNull @Size(min = 2, max = 2) List<@NotNull @Size(min = 12,
            max = 28) List<@NotBlank @Size(max = 100000) String>> batches) {
    }

    /**
     * 开启一次活体挑战。
     * @param context 登录上下文
     * @param request 请求
     * @param response 响应
     * @return 随机动作
     */
    @PostMapping("/challenge")
    @RateLimiter(name = "training:face:challenge", rate = 8, interval = 1, unit = TimeUnit.MINUTES,
        type = LimitType.IP, message = "活体尝试过于频繁，请稍后再试")
    public FaceLivenessService.Challenge challenge(@RequestBody @Valid Context context,
        HttpServletRequest request, HttpServletResponse response) {
        response.setHeader("Cache-Control", "no-store");
        return liveness.start(scope(context, request));
    }

    /**
     * 核验连续画面。
     * @param input 采集内容
     * @param request 请求
     * @param response 响应
     * @return 一次性登录凭证
     */
    @PostMapping("/verify")
    @RateLimiter(name = "training:face:liveness", rate = 8, interval = 1, unit = TimeUnit.MINUTES,
        type = LimitType.IP, message = "活体尝试过于频繁，请稍后再试")
    public FaceLivenessService.Proof verify(@RequestBody @Valid VerifyRequest input,
        HttpServletRequest request, HttpServletResponse response) {
        response.setHeader("Cache-Control", "no-store");
        return liveness.verify(input.challengeId(), input.batches(),
            scope(input.context(), request), tenant());
    }

    public record ProgressRequest(@NotBlank @Size(max = 36) String challengeId,
        int step, @NotNull @Valid Context context,
        @NotNull @Size(min = 12, max = 28) List<@NotBlank @Size(max = 100000) String> frames) {
    }

    /**
     * 检查动作完成情况，未完成时停留在当前步骤。
     * @param input 采集内容
     * @param request 请求
     * @param response 响应
     * @return 完成状态
     */
    @PostMapping("/progress")
    @RateLimiter(name = "training:face:progress", rate = 30, interval = 1, unit = TimeUnit.MINUTES,
        type = LimitType.IP, message = "活体检测过于频繁，请稍后重试")
    public boolean progress(@RequestBody @Valid ProgressRequest input,
        HttpServletRequest request, HttpServletResponse response) {
        response.setHeader("Cache-Control", "no-store");
        return liveness.progress(input.challengeId(), input.step(), input.frames(),
            scope(input.context(), request), tenant());
    }

    private String scope(Context context, HttpServletRequest request) {
        return liveness.scope(tenant(), context.clientId(), context.identify(), context.username(),
            request.getRemoteAddr());
    }

    private static Long tenant() {
        return TenantContextHolder.isTenantEnabled() ? TenantContextHolder.getTenantId()
            : Long.valueOf(0L);
    }
}
