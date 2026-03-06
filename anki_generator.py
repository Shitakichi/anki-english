import json
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
import sys

class AnkiCardGenerator:
    def __init__(self, config_path='config.json'):
        """設定ファイルを読み込んで初期化"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.db_path = self.config['database']['path']
        self.ollama_url = self.config['ollama']['base_url']
        self.ollama_model = self.config['ollama']['model']
        self.anki_url = self.config['anki']['connect_url']
        self.deck_name = self.config['anki']['deck_name']
        
    def read_input_file(self, filepath):
        """入力テキストファイルを読み込む"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        return content
    
    def generate_html_with_llm(self, raw_text):
        """OllamaのLLMを使ってHTML断片を生成"""
        
        prompt = f"""あなたは英語学習用のAnkiカード生成アシスタントです。
以下の単語情報から、HTMLコンテンツ部分のみを生成してください。

入力テキスト:
{raw_text}

生成ルール:
1. 単語名は <div class="word-title">単語</div> で囲む
2. 品詞ごとに以下の形式で出力:
   <div class="pos-section">
     <span class="pos-label">品詞名</span>
     <span class="pos-meanings">意味1、意味2、意味3</span>
   </div>
3. コアイメージがあれば:
   <div class="core-image">
     <div class="core-image-label">コアイメージ</div>
     <div class="core-image-text">イメージ内容</div>
   </div>
4. 派生語があれば:
   <div class="derivatives">
     <div class="derivatives-label">派生語</div>
     <ul class="derivatives-list">
       <li>単語(意味)</li>
     </ul>
   </div>

注意:
- <html>、<body>、<style>タグは含めない
- 純粋なコンテンツ部分のみ出力
- 日本語の説明文は一切不要
- HTMLコードのみを出力

出力:"""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            generated_html = result['response'].strip()
            
            # コードブロックのマークダウン記法を除去
            if generated_html.startswith('```html'):
                generated_html = generated_html.replace('```html', '').replace('```', '').strip()
            elif generated_html.startswith('```'):
                generated_html = generated_html.replace('```', '').strip()
            
            return generated_html
            
        except Exception as e:
            print(f"❌ LLM生成エラー: {e}")
            return None
    
    def wrap_with_template(self, content_html):
        """生成されたHTMLをテンプレートに埋め込む"""
        template_path = self.config['templates']['word_template']
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        return template.replace('{{CONTENT}}', content_html)
    
    def save_to_database(self, source_file, raw_input, generated_html, status='pending'):
        """データベースに保存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO cards (source_file, category, raw_input, generated_html, deck_name, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (source_file, '単語', raw_input, generated_html, self.deck_name, status))
        
        card_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return card_id
    
    def add_to_anki(self, front_html, card_id):
        """AnkiConnectを使ってAnkiに追加"""
        
        # デッキ作成（存在しない場合）
        deck_payload = {
            "action": "createDeck",
            "version": 6,
            "params": {
                "deck": self.deck_name
            }
        }
        
        try:
            requests.post(self.anki_url, json=deck_payload)
        except:
            pass  # デッキが既に存在する場合はエラーになるが無視
        
        # ノート追加
        note_payload = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": self.deck_name,
                    "modelName": "Basic",
                    "fields": {
                        "Front": front_html,
                        "Back": ""  # 1面型なのでBackは空
                    },
                    "tags": ["auto-generated", "english-learning"]
                }
            }
        }
        
        try:
            response = requests.post(self.anki_url, json=note_payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('error'):
                print(f"❌ Anki追加エラー: {result['error']}")
                return None
            
            anki_note_id = result.get('result')
            
            # データベース更新
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE cards SET anki_note_id = ?, status = 'added'
                WHERE id = ?
            ''', (anki_note_id, card_id))
            conn.commit()
            conn.close()
            
            return anki_note_id
            
        except Exception as e:
            print(f"❌ AnkiConnect通信エラー: {e}")
            return None
    
    def process_file(self, input_filepath):
        """1つのテキストファイルを処理"""
        print(f"\n{'='*60}")
        print(f"📄 処理中: {input_filepath}")
        print(f"{'='*60}\n")
        
        # 1. ファイル読み込み
        raw_text = self.read_input_file(input_filepath)
        print(f"✅ 入力テキスト読み込み完了\n")
        print("--- 入力内容 ---")
        print(raw_text)
        print("-" * 60 + "\n")
        
        # 2. LLMでHTML生成
        print("🤖 LLMでHTML生成中...")
        content_html = self.generate_html_with_llm(raw_text)
        
        if not content_html:
            print("❌ HTML生成失敗")
            return None
        
        print("✅ HTML生成完了\n")
        print("--- 生成されたHTML ---")
        print(content_html)
        print("-" * 60 + "\n")
        
        # 3. テンプレート適用
        full_html = self.wrap_with_template(content_html)
        
        # 4. データベース保存
        source_filename = Path(input_filepath).name
        card_id = self.save_to_database(source_filename, raw_text, full_html)
        print(f"✅ データベース保存完了 (ID: {card_id})\n")
        
        # 5. プレビュー保存
        preview_path = f"output/preview_{card_id}.html"
        with open(preview_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        print(f"✅ プレビューファイル保存: {preview_path}\n")
        
        # 6. 確認UI
        print("=" * 60)
        print("📋 確認")
        print("=" * 60)
        print(f"プレビュー: {preview_path} をブラウザで開いて確認してください")
        
        while True:
            choice = input("\nAnkiに追加しますか? (y/n/q=終了): ").strip().lower()
            
            if choice == 'y':
                print("\n📤 Ankiに追加中...")
                anki_id = self.add_to_anki(full_html, card_id)
                
                if anki_id:
                    print(f"✅ Anki追加成功! (Note ID: {anki_id})")
                    return card_id
                else:
                    print("❌ Anki追加失敗")
                    return None
                    
            elif choice == 'n':
                print("⏭️  スキップしました")
                return card_id
                
            elif choice == 'q':
                print("👋 終了します")
                sys.exit(0)
                
            else:
                print("❌ y/n/q のいずれかを入力してください")

def main():
    """メイン処理"""
    print("\n" + "=" * 60)
    print("🎴 Anki英語学習カード自動生成システム - Phase 1")
    print("=" * 60 + "\n")
    
    # 引数チェック
    if len(sys.argv) < 2:
        print("使用方法: python anki_generator.py <入力ファイルパス>")
        print("例: python anki_generator.py input/present.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not Path(input_file).exists():
        print(f"❌ ファイルが見つかりません: {input_file}")
        sys.exit(1)
    
    # ジェネレーター初期化
    generator = AnkiCardGenerator()
    
    # 処理実行
    result = generator.process_file(input_file)
    
    if result:
        print("\n" + "=" * 60)
        print("✅ 処理完了!")
        print("=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print("⚠️  処理が完了しましたが、一部エラーがありました")
        print("=" * 60 + "\n")

if __name__ == "__main__":
    main()