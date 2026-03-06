# Anki英語学習カード自動生成システム - Phase 1

OllamaのローカルLLMを使って、英語学習用のAnkiカードを自動生成するシステムです。

## 📁 ディレクトリ構成

```
anki-english/
├── input/              # 入力テキストファイルを配置
│   └── present.txt     # サンプルファイル
├── output/             # 生成されたプレビューHTMLの保存先
├── templates/          # AnkiカードのHTMLテンプレート
│   └── word_card.html
├── anki_generator.py   # メインスクリプト
├── init_db.py          # データベース初期化
├── config.json         # 設定ファイル
├── database.db         # SQLiteデータベース(初回実行後に生成)
└── README.md           # このファイル
```

## 🚀 セットアップ手順

### 1. 前提条件

- Python 3.8以上
- Ollama (インストール済み)
- Anki (起動中)
- AnkiConnect アドオン (Ankiにインストール済み)

### 2. Ollamaのモデル準備

```bash
# Qwen 2.5 3Bモデルをダウンロード
ollama pull qwen2.5:3b
```

### 3. AnkiConnectのインストール

1. Ankiを開く
2. メニュー > ツール > アドオン
3. 「アドオンを取得」をクリック
4. コード `2055492159` を入力してOK
5. Ankiを再起動

### 4. データベース初期化

```bash
cd anki-english
python init_db.py
```

### 5. 必要なPythonパッケージのインストール

```bash
pip install requests --break-system-packages
```

## 📝 使い方

### 基本的な流れ

1. **入力ファイルを作成**
   
   `input/` フォルダに `.txt` ファイルを作成します。
   
   ```txt
   単語: present
   
   【名詞】現在、存在、贈り物
   【動詞】与える、差し出す
   【形容詞】現在の、出席している
   
   コアイメージ: 目の前に差し出す
   
   派生語: presentation(発表、表示), presently(現在、まもなく), presence(存在、出席)
   ```

2. **Ankiを起動しておく**

3. **スクリプトを実行**
   
   ```bash
   python anki_generator.py input/present.txt
   ```

4. **確認と追加**
   
   - 生成されたHTMLプレビューが `output/` に保存されます
   - ブラウザでプレビューを確認
   - CLI上で `y` を入力するとAnkiに追加されます

### コマンド例

```bash
# サンプルファイルで試す
python anki_generator.py input/present.txt

# 自分で作成したファイルを処理
python anki_generator.py input/my_word.txt
```

## ⚙️ 設定

`config.json` で以下を変更できます:

- **Ollamaモデル**: `qwen2.5:3b` から別のモデルに変更可能
- **Ankiデッキ名**: デフォルトは `英語学習v1`
- **AnkiConnectのURL**: デフォルトは `http://localhost:8765`

## 🗄️ データ管理

生成履歴は `database.db` に保存されます。

```bash
# データベースの中身を確認
sqlite3 database.db "SELECT * FROM cards;"
```

## 🐛 トラブルシューティング

### Ollamaに接続できない

```bash
# Ollamaが起動しているか確認
ollama list

# 起動していない場合
ollama serve
```

### AnkiConnectに接続できない

1. Ankiが起動しているか確認
2. AnkiConnectアドオンがインストールされているか確認
3. ファイアウォールでポート8765がブロックされていないか確認

### LLMの生成結果がおかしい

- `config.json` で別のモデル (例: `gemma2:9b`, `llama3.1:8b`) に変更してみる
- プロンプトの調整が必要な場合は `anki_generator.py` の `generate_html_with_llm()` メソッド内のプロンプトを編集

## 📊 Phase 1の制限事項

- ✅ 単語カテゴリのみ対応
- ✅ 1ファイル = 1カード
- ✅ CLI確認UI
- ❌ 複数項目の一括処理 (Phase 2で実装予定)
- ❌ 文法・イディオム対応 (Phase 2で実装予定)
- ❌ 自動難易度調整 (Phase 3で実装予定)

## 🔜 次のステップ (Phase 2)

- 複数カテゴリ対応 (文法、イディオム)
- 1ファイル内の複数項目を一括処理
- ブラウザプレビューUI
- HTMLテンプレート自動選択

## 📄 ライセンス

個人使用のみ