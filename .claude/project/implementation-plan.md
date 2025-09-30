# 実装計画 (Implementation Plan) ⚡

CI/CD Insights Dashboardの実装手順です。

---

## MVP実装（1週間目標）

### 実装ステップ
1. **環境準備**
   ```bash
   pip install flask requests
   ```

2. **GitHub APIデータ取得**
   - Personal Access Tokenでワークフロー実行データ取得
   - JSONで実行履歴を保存

3. **SQLiteデータベース**
   - workflows, runsテーブル作成
   - 基本的なCRUD操作

4. **Flaskウェブアプリ**
   - HTMLテンプレートでメトリクス表示
   - 期間フィルタリング機能

### ファイル構成
```
cicd_dashboard/
├── app.py              # メインFlaskアプリ
├── data_collector.py   # GitHub API接続
├── database.py         # SQLite操作
├── config.py          # 設定（API token等）
├── templates/
│   └── dashboard.html  # メインダッシュボード
└── static/
    └── style.css       # 基本CSS
```

---

## 基本機能

### データ収集
- GitHub Actions Workflow Runs API呼び出し
- 1日1回の手動実行（cronは後で追加）
- エラーハンドリング（API制限・ネットワーク障害）

### メトリクス計算
- **Duration**: 平均実行時間
- **Success Rate**: 成功 ÷ (成功 + 失敗)
- **Throughput**: 日次・週次実行回数
- **MTTR**: 失敗から次回成功までの時間

### 表示機能
- 基本的なHTML表
- 期間選択（過去7日・30日）
- リポジトリ別フィルタリング

---

## 成功基準

### 動作確認
- [ ] GitHub APIからデータ取得できる
- [ ] SQLiteに正しくデータ保存される
- [ ] Webページで基本メトリクス表示される
- [ ] フィルタリングが動作する

### 実用性確認
- [ ] 自分のリポジトリで意味のある結果が出る
- [ ] 1週間分のデータで傾向が分かる
- [ ] 改善点が特定できる

---

## 技術考慮事項

### セキュリティ
- Personal Access Tokenを環境変数で管理
- SQLiteファイルの適切な権限設定

### パフォーマンス
- 必要な期間のデータのみ取得
- シンプルなSQL集計で高速レスポンス

### エラー処理
- GitHub API制限のリトライ機能
- 不正データの除外

---

この最小構成で実用的なダッシュボードを1週間以内に構築できます。