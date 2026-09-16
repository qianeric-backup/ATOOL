**心理测评自动答题工具**  
**功能**  
| | |  
|-|-|  
| **功能** | **说明** |   
| 自动登录 | 学号 + 密码（默认 学号#），账号/密码经 RSA(PKCS1v1.5) 加密提交，复现前端 jsencrypt 逻辑 |   
| 验证码自动处理 | 该站验证码为前端生成文本（#code_box），自动读取；若部署为真图片验证码，自动调用 ddddocr OCR |   
| 自动探测待测项 | GetPublishTest 拉取发布量表，IsTest=0 且 IsCanTest=1 标记为"待测试" |   
| 拉取全部题目 | GetPaperAllInfo 取回题目、选项、分值、跳题规则 |   
| AI 最健康作答 | 规则求解器：①模板命中 ②选项症状分最低 ③极性启发（症状题→否认 / 积极题→肯定 / 程度量表→最轻档） ④中间项兜底并提示人工复核 |   
| 固化选择（模板） | 一键把当前作答写入 config/template.json（按题面文本为键） |   
| 导入/导出配置 | 模板 JSON 可发给他人 → 导入后同量表直接复用，无需重新思考 |   
| 一键提交 | 逐量表按原前端协议 SumitPaperInfo 提交，含拟真逐题时间戳（默认随机 2~6 秒/题） |   
| 逐题可改 | 决策表双击"选择"列循环切 A/B/C…，改完可重新固化 |   
   
**使用**  
./run_gui.sh                        # 一键启动(Linux): 自动装依赖到 ./pylibs,  
                                     # 自动补齐 Qt x11 所需 libxcb-cursor0(免root)  
 pip install -r requirements.txt     # 或手动安装后: python main.py  
   
GUI 操作顺序：  
1. 输入学号（密码自动 学号#，可手改）→ 点 **登录**  
2. 登录成功自动 **探测待测项**（也可手动点"自动探测待测项"）  
3. 勾选要做的量表 → 点 **拉取题目并AI作答**？——按钮为流程第 3 步（见下）：探测成功后  
 *双击待测行* 或勾选后点 **提交所选量表**，程序会自动拉题→AI作答→拟真提交  
4. **固化当前选择到模板**：把本次 AI 选择写入本地模板  
5. **导出配置**：把 template.json 发给同学；同学  **导入配置** 后登录自己账号、  
   
 探测待测项，同量表题目将自动命中模板作答  
命令行（等价流程，适合批量）：  
# 只作答并固化, 不提交  
 python headless_run.py --account 学号  
 # 作答并直接提交  
 python headless_run.py --account 学号 --submit  
 # 指定策略: 最健康 / fixed:A / fixed:B  
 python headless_run.py --account 学号 --strategy fixed:B --submit  
   
**首次运行结果（账号 2611999，张三）**  
平台"2026 新生测试"发布任务：卡特尔 16PF（187 题，此前已完成）+ 大学生人格测验  
   
 UPI（64 题）。  
- UPI 已由本工具完成提交，平台状态已翻转为 **已完成**  
- 64 题 AI 选择：56 道症状题 → B 否；4 道积极表述测谎题（5/20/35/50）→ A 有；  
   
 4 道附加题（61-64）→ B 没有。UPI 症状总分 = 0，属于最健康档  
- 选择已固化至 config/template.json，可直接导出复用  
**模板格式**  
{  
   "version": 2,  
   "updated_at": "2026-09-15 09:01:xx",  
   "papers": {  
     "大学生人格测验（UPI）": {  
       "paper_id": "4419d764-…",  
       "paper_name": "大学生人格测验（UPI）",  
       "answers": {  
         "食欲不振": {"number":1,"question":"食欲不振","opt":"B",  
                    "option_name":"否","answer_id":"dd1ee0ef-…","reason":"最低症状分(0)"}  
       }  
     }  
   }  
 }  
   
模板命中规则：题面全覆盖归一化精确匹配 → 相似度 ≥0.92 模糊匹配；未命中走求解器规则。  
**本地 mock（离线测试，不碰真实站点）**  
./run_mock.sh            # 启动 mock(127.0.0.1:18085) + 打开 GUI 并指向 mock  
 ./run_mock.sh --no-gui   # 只跑 mock 后台, GUI 站点地址手填 http://127.0.0.1:18085  
   
- 数据源：mock_data/ = 真实站点抓取原文（16PF 187题 + UPI 64题 + 用户信息 + 发布清单）  
- 行为复现：双层 JSON 编码、任意账密登录放行、GetPaperAllInfo 回放、  
 SumitPaperInfo 后量表状态翻转为"已完成"（状态存 mock/mock_state.json）  
- 重置测试态：rm mock/mock_state.json → UPI 恢复"待测试"  
- tools/save_mock_data.py：需要更新数据时用真实账号重新抓取  
**目录结构**  
core/client.py    HTTP 客户端（登录RSA/验证码/探测/拉题/提交/暂存）  
 core/solver.py    最健康作答求解器 + 模板固化  
 core/store.py     模板 JSON 读写、导入导出、账号记忆（不存密码）  
 main.py           PySide6 GUI  
 headless_run.py   命令行批处理入口  
 config/           运行时生成: template.json / profile.json  
 probe/            逆向探测过程中的站点协议样本(HTML/JS/JSON)  
   
**站点协议速查（逆向结论）**  
- POST /Home/UserLoginaccount=RSA(学号), PWD=RSA(密码) —— 服务端不校验验证码  
- POST /Home/CheckLogin → Code=-1 未登录  
- POST /PsyTest/GetPublishTestVersion=0 → 发布量表（含 IsTest/IsCanTest）  
- POST /PsyTest/GetPaperAllInfoPaperID,IsTemp=1,PublishId,ComTypCode → 题目全集  
- POST /PsyTest/SumitPaperInfo（注意站点拼写 Sumit）  
 TmpResult = ";QuestionId|AnswerId|Start|End||0"…，ModuleId=APP, IsSimple=1  
- 接口返回双层 JSON 编码（字符串里再套 JSON），已用 deep_json 兼容  
