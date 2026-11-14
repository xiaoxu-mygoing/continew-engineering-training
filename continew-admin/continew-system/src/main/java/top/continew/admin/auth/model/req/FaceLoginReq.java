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

package top.continew.admin.auth.model.req;

import lombok.Getter;
import lombok.Setter;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.io.Serial;

/**
 * 人脸登录采集请求。
 *
 * @author 工程实训小组
 * @since 4.2.0
 */
@Getter
@Setter
public class FaceLoginReq extends LoginReq {

    @Serial
    private static final long serialVersionUID = 1L;

    @Size(max = 64)
    private String username;

    private boolean identify;

    @NotBlank
    @Size(max = 450000, message = "采集画面过大")
    private String image;
}
