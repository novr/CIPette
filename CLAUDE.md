# CLAUDE.md

AI開発ガイド: CIPetteプロジェクトでの作業指針

## プロジェクト概要

**CIPette** - GitHub ActionsのCI/CDメトリクスを可視化するシンプルなダッシュボード

**目標**: 5分でCI/CDインサイトを取得（5時間ではなく）

> 📖 **ユーザー向け情報は[README.md](README.md)を参照**

## コア機能

- GitHub Actionsワークフローデータの収集
- 4つの主要メトリクス計算: Duration, Success Rate, Throughput, MTTR
- シンプルなWebテーブル表示
- 期間・リポジトリ別フィルタリング

## 技術構成

- **Python 3.11+** + Flask
- **SQLite** データベース
- **uv** パッケージ管理
- **PyGithub** GitHub API

## ファイル構成

```
cipette/
├── app.py              # Webダッシュボード（Flask）
├── collector.py         # GitHubデータ収集
├── database.py          # SQLite操作
├── config.py            # 設定管理
├── data_processor.py    # メトリクス計算
├── etag_manager.py      # ETagキャッシュ
├── github_client.py     # GitHub APIクライアント
├── retry.py             # リトライロジック
├── sql_security.py      # SQLインジェクション対策
└── error_handling.py    # エラーハンドリング
```

## AI作業指針

### コード品質
- **必ずリンター実行**: `uv run ruff check cipette/ tests/ --fix`
- 修正後は `uv run ruff check cipette/ tests/` で確認
- 型ヒントを一貫して使用
- PEP 8スタイルガイドラインに従う

### 重要な実装ポイント

#### データベース操作
- `DatabaseConnection`コンテキストマネージャーを使用
- `sql_security.py`でSQLインジェクション対策済み
- `retry.py`でリトライロジック実装

#### GitHub API統合
- レート制限は自動的にリトライロジックで処理
- ETagキャッシュで効率的なデータ取得
- エラーハンドリングとログ出力

#### パフォーマンス
- MTTR計算はキャッシュ済み
- メトリクスはメモリキャッシュ（TTL付き）
- データベース接続プール使用

### テスト実行
- `uv run pytest` でテスト実行
- `tests/`ディレクトリにユニットテスト

## 現在の実装状況

- [x] GitHub Actionsデータ収集
- [x] Webインターフェース表示
- [x] フィルタリング機能
- [x] 高速パフォーマンス
- [x] コード品質維持
- [x] エラーハンドリング・リトライ
- [x] SQLインジェクション対策
- [ ] 実データからの有用なインサイト

**方針**: 動作するソフトウェアを素早くリリース、最適化は後で