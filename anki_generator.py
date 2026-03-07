import json
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
import sys
import os

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

        prompt_path = self.config.get('prompts', {}).get('word_prompt', 'prompts/word_prompt.json')
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.word_prompt_config = json.load(f)
        
    def read_input_file(self, filepath):
        """入力テキストファイルを読み込む"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        return content
    
    def generate_json_with_llm(self, raw_text):
        """OllamaのLLMを使ってJSON形式でデータを生成"""
    
        # Few-shotプロンプトを構築
        prompt_config = self.word_prompt_config
        
        # システム指示
        prompt_parts = [prompt_config['system_instruction'], "\n"]
        
        # 出力形式の説明
        prompt_parts.append("## 出力形式\n")
        prompt_parts.append(json.dumps(prompt_config['output_format']['schema'], ensure_ascii=False, indent=2))
        prompt_parts.append("\n\n")
        
        # ルール
        prompt_parts.append("## ルール\n")
        for rule in prompt_config['rules']:
            prompt_parts.append(f"- {rule}\n")
        prompt_parts.append("\n")
        
        # Few-shot例
        prompt_parts.append("## 例\n\n")
        for i, example in enumerate(prompt_config['examples'], 1):
            prompt_parts.append(f"### 例{i}\n")
            prompt_parts.append(f"入力:\n{example['input']}\n\n")
            prompt_parts.append(f"出力:\n{json.dumps(example['output'], ensure_ascii=False, indent=2)}\n\n")
        
        # 実際の処理対象
        prompt_parts.append("## 実際の処理\n")
        prompt_parts.append(f"入力:\n{raw_text}\n\n")
        prompt_parts.append("出力:\n")
        
        prompt = "".join(prompt_parts)
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=90  # Few-shotで長くなるのでタイムアウト延長
            )
            response.raise_for_status()
            result = response.json()
            generated_text = result['response'].strip()
            
            # コードブロックのマークダウン記法を除去
            if generated_text.startswith('```json'):
                generated_text = generated_text.replace('```json', '').replace('```', '').strip()
            elif generated_text.startswith('```'):
                generated_text = generated_text.replace('```', '').strip()
            
            # JSONパース
            try:
                data = json.loads(generated_text)
                return data
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析エラー: {e}")
                print(f"LLM出力:\n{generated_text}")
                return None
            
        except Exception as e:
            print(f"❌ LLM生成エラー: {e}")
            return None
        
    def convert_json_to_html(self, data):
        """JSONデータからHTMLコンテンツを生成"""
        html_parts = []
        
        # 単語タイトル
        html_parts.append(f'<div class="word-title">{data["word"]}</div>')
        
        # 品詞セクション
        for pos_section in data.get("pos_sections", []):
            pos = pos_section.get("pos", "")
            meanings = pos_section.get("meanings", [])
            meanings_text = "、".join(meanings)
            
            html_parts.append(f'''<div class="pos-section">
        <span class="pos-label">{pos}</span>
        <span class="pos-meanings">{meanings_text}</span>
    </div>''')
        
        # コアイメージ
        core_image = data.get("core_image")
        if core_image:
            html_parts.append(f'''<div class="core-image">
        <div class="core-image-label">コアイメージ</div>
        <div class="core-image-text">{core_image}</div>
    </div>''')
        
        # 派生語
        derivatives = data.get("derivatives")
        if derivatives:
            html_parts.append('''<div class="derivatives">
        <div class="derivatives-label">派生語</div>
        <ul class="derivatives-list">''')
            
            for deriv in derivatives:
                word = deriv.get("word", "")
                meaning = deriv.get("meaning", "")
                html_parts.append(f'        <li>{word}({meaning})</li>')
            
            html_parts.append('''    </ul>
    </div>''')
        
        # 例文
        examples = data.get("examples")
        if examples:
            html_parts.append('''<div class="examples">
        <div class="examples-label">例文</div>
        <ul class="examples-list">''')
            
            for example in examples:
                html_parts.append(f'        <li>{example}</li>')
            
            html_parts.append('''    </ul>
    </div>''')
        
        return "\n".join(html_parts)
    
    def wrap_with_template(self, content_html, for_anki=False):  # ← for_anki引数を追加
        """生成されたHTMLをテンプレートに埋め込む
        
        Args:
            content_html: コンテンツHTML
            for_anki: True=Anki用(コンテンツのみ), False=プレビュー用(CSS含む)
        """
        if for_anki:
            # Anki用: コンテンツのみ (Anki側でスタイル適用)
            return content_html
        
        # プレビュー用: CSS含む完全版
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
        model_name = self.config['anki'].get('model_name', 'English Learning Card')

        note_payload = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": self.deck_name,
                    "modelName": model_name,  # ← カスタムモデルを使用
                    "fields": {
                        "Front": front_html,
                        "Back": ""  # 1面型なのでBackは空
                    },
                    "tags": ["auto-generated", "english-learning"],
                    "options": {
                        "allowDuplicate": False
                    }
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
        
        # 2. LLMでJSON生成
        print("🤖 LLMでJSON生成中...")
        json_data = self.generate_json_with_llm(raw_text)

        if not json_data:
            print("❌ JSON生成失敗")
            return None

        print("✅ JSON生成完了\n")
        print("--- 生成されたJSON ---")
        print(json.dumps(json_data, ensure_ascii=False, indent=2))
        print("-" * 60 + "\n")

        # 3. JSONからHTMLに変換
        print("🔄 HTMLに変換中...")
        content_html = self.convert_json_to_html(json_data)
        print("✅ HTML変換完了\n")
        
        # 4. テンプレート適用
        full_html_preview = self.wrap_with_template(content_html, for_anki=False)  # プレビュー用
        full_html_anki = self.wrap_with_template(content_html, for_anki=True)     # Anki用
        
        # 5. データベース保存
        source_filename = Path(input_filepath).name
        card_id = self.save_to_database(source_filename, raw_text, full_html_anki)  # Anki用を保存
        print(f"✅ データベース保存完了 (ID: {card_id})\n")

        # 6. プレビュー保存
        preview_path = f"output/preview_{card_id}.html"
        with open(preview_path, 'w', encoding='utf-8') as f:
            f.write(full_html_preview)  # プレビュー用を保存
        print(f"✅ プレビューファイル保存: {preview_path}\n")

        # 7. 確認UI
        print("=" * 60)
        print("📋 確認")
        print("=" * 60)
        print(f"プレビュー: {preview_path} をブラウザで開いて確認してください")

        while True:
            choice = input("\nAnkiに追加しますか? (y/n/q=終了): ").strip().lower()
            
            if choice == 'y':
                print("\n📤 Ankiに追加中...")
                anki_id = self.add_to_anki(full_html_anki, card_id)  # Anki用を送信
                
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