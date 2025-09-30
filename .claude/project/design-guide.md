# 設計ガイド (Design Guide) 🏗️

## 設計原則

- **シンプル第一**: 最小限の機能で動作するものを優先
- **早期価値提供**: 完璧性より実用的な結果を重視
- **学習コスト最小**: 既知の技術で迅速な開発

---

### MVP構成

| 領域 | 技術 | 理由 |
|------|------|------|
| **言語** | Python 3 | 豊富なライブラリ、GitHub API対応 |
| **Web** | Flask | 軽量、学習コスト低、迅速開発 |
| **データベース** | SQLite | ファイルベース、設定不要、軽量 |
| **UI** | HTML/CSS | シンプル、デザイン不要、高速表示 |
| **実行** | ローカル | Docker不要、環境構築最小 |

**選定方針**: 設定ファイル・環境構築・学習コストを最小化

---

## データ構造

### シンプルなテーブル設計
```sql
-- ワークフロー基本情報
CREATE TABLE workflows (
  id TEXT PRIMARY KEY,
  repository TEXT,
  name TEXT
);

-- 実行履歴（データ集計用）
CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT,
  commit_sha TEXT,
  branch TEXT,
  status TEXT,  -- 'success', 'failure', 'cancelled'
  started_at DATETIME,
  completed_at DATETIME
);
```

**設計方針**: 複雑なリレーションシップを避け、集計に必要な最小データのみ

---

## 基本メトリクス

### 計算ロジック
- **Duration**: `completed_at - started_at` の平均
- **Success Rate**: `成功回数 ÷ (成功 + 失敗) × 100`
- **Throughput**: 期間あたりの完了回数
- **MTTR**: 失敗後の次回成功までの時間

**注意**: 複雑なビジネスルールは適用せず、シンプルな集計のみ

---

## 実装アプローチ

### 段階的開発
1. **GitHub API接続**: 基本データ取得
2. **SQLite保存**: ローカルデータ蓄積
3. **HTML表示**: 基本メトリクス可視化
4. **フィルタリング**: 期間・ブランチ絞込み

### ファイル構成
```
cicd_dashboard/
├── app.py              # Flask アプリケーション
├── data_collector.py   # GitHub API データ取得
├── database.py         # SQLite 操作
├── config.py          # 設定（API token等）
├── templates/
│   └── dashboard.html  # メインダッシュボード
└── static/
    └── style.css       # 最小限CSS（50行程度）
```

---

## HTML/CSS シンプルUI実現

### UI設計原則
- **フレームワーク不要**: Bootstrap等使わずプレーンHTML/CSS
- **テーブル中心**: データ表示はHTML tableで十分
- **最小限CSS**: 見やすさ重視、装飾は最小限
- **フィルタリング**: selectボックスとtextフィールドのみ

### 表示内容
```html
<!-- 基本レイアウト -->
フィルター（期間・リポジトリ選択）
    ↓
メトリクステーブル
├─ リポジトリ名
├─ Success Rate（色分け表示）
├─ 平均Duration（分）
├─ Throughput（回/日）
└─ MTTR（分）
```

### CSS方針
- **50行以内**: 必要最小限のスタイル
- **色分け**: Success Rate の良/悪を緑/赤で表示
- **ホバー効果**: テーブル行のマウスオーバー
- **シンプル配色**: 白背景・黒文字・アクセント1色

**方針**: 1週間で動作するプロトタイプを目標

---

この構成により、学習コスト最小で実用的な **CIPette** を迅速に構築できます。