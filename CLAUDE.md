# CLAUDE.md

AI開発ガイド: CIPetteプロジェクトでの作業指針

## プロジェクト概要

**CIPette** - GitHub ActionsのCI/CDメトリクスを可視化するシンプルなダッシュボード

**目標**: 5分でCI/CDインサイトを取得

## コア機能

- GitHub Actionsデータ収集
- ヘルススコア計算（0-100点）
- データ品質評価（5段階）
- Webダッシュボード表示

## AI作業指針

### コード品質
- **必ずリンター実行**: `uv run ruff check cipette/ tests/ --fix`
- 型ヒントを一貫して使用
- PEP 8スタイルガイドラインに従う

### テスト実行
- `uv run pytest` でテスト実行

**方針**: 動作するソフトウェアを素早くリリース