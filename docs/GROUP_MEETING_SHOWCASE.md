# TeachIntent 组会现场操作

1. 项目根目录运行 `scripts/start_showcase.sh`，打开输出的
   `http://127.0.0.1:<frontend-port>/showcase`。远程电脑按脚本打印的 SSH
   tunnel 命令转发后打开同一地址。端口以本次启动输出为准。
2. 默认先展示 **Corrective Feedback**：左侧看学生将“速度大小不变”
   误判为“加速度为零”，中间看真实 v0.2 计划的 WHAT / HOW。
3. 展开 **View evaluator details**，展示六维评分与原始证据。切换
   **Scaffolding** 看配子提示，再切换 **Supportive Feedback** 看合理的
   空 delivery。点击 Neutral / Planned 播放录音；不会自动播放。
4. 30–60 秒讲法：“一般流程是情境到文本再到语音。TeachIntent 显式加入
   学生状态和教学意图，让 Hy3 产出结构化 Speech Plan，把说什么与怎么说
   分开。独立 Evaluator 检查计划并给出证据，不评分 WAV。这里是已有真实
   v0.2 案例；当前规划器也支持 v0.3/v0.4。没有必要时不强行增加语音控制。”
5. 追问语音执行时，指向 **Speech Execution**：已观察到 single-pass
   漂移，segmented 按段独立合成并顺序播放。点击 **Open Live Studio**
   进入已有实验入口；公开 A/B 是早期 Qwen3-TTS 录音，不冒充实时 Baton。
6. Live Generate 需要可用的服务端 provider 配置；Baton 还需要独立运行时。
   API 不稳定时直接点导航 **Showcase** 返回三个稳定案例。Showcase 不需要
   OpenRouter、Hy3 API、GPU 或模型。无需现场重跑实验。

停止时运行 `scripts/stop_showcase.sh`；日志与 PID 记录位于
`outputs/showcase-runtime/`，启动脚本只管理自己创建的两个服务。
