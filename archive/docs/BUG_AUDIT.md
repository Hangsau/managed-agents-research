# Managed-Agents Bug Audit

## P0 Critical
1. **Docker /workspace 路徑映射不同步**
   - docker_exec.py 只掛載 `workdir:/workspace`，container 內的 `/tmp` 是空的
   - agent `read_file` 讀 host，`bash` 跑 container，看到的文件系統不一致
   - 修復：掛載 `/tmp:/tmp` 進 container

2. **call_llm fallback 返回 JSON 字串導致解析異常**
   - 所有模型失敗後返回 `json.dumps({"error": ...})`
   - run_turn 的 `json.loads(raw)` 成功解析但缺少 thought/action
   - 修復：返回 None 或 raise

3. **get_events json.loads 崩潰**
   - payload 損壞時 `json.loads(r[3])` 抛 JSONDecodeError
   - 修復：try/except 保護

## P1 High
4. 缺少 web_search action
5. 缺少 search_files action
6. write_file 缺少 encoding="utf-8"
7. datetime.utcnow() deprecated
8. run_agent.py error 處理不一致

## P2 Medium
9. guard 路徑硬編碼
10. history 剖析邏輯誤判 markdown
11. stuck loop 閾值太低（4 個）
