import os
import shutil
from werkzeug.utils import secure_filename
import config
from typing import Optional

class FileHandler:
    def __init__(self):
        self.upload_folder = config.UPLOAD_FOLDER
        self.allowed_extensions = config.ALLOWED_EXTENSIONS
    
    def allowed_file(self, filename: str) -> bool:
        """检查文件扩展名是否允许"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def save_uploaded_file(self, file) -> Optional[str]:
        """保存上传的文件"""
        if file and self.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # 确保上传目录存在
            os.makedirs(self.upload_folder, exist_ok=True)
            
            # 生成唯一的文件名
            timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
            base_name, ext = os.path.splitext(filename)
            unique_filename = f"{base_name}_{timestamp}{ext}"
            
            filepath = os.path.join(self.upload_folder, unique_filename)
            file.save(filepath)
            
            return filepath
        
        return None
    
    def delete_file(self, filepath: str) -> bool:
        """删除文件"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    
    def cleanup_old_files(self, days: int = 7):
        """清理旧文件"""
        import time
        
        current_time = time.time()
        
        for folder in [self.upload_folder, config.VECTOR_DB_PATH, config.TERMINOLOGY_DB_PATH]:
            if not os.path.exists(folder):
                continue
                
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                
                # 跳过目录和重要文件
                if os.path.isdir(filepath):
                    continue
                if filename in ['faiss_index.bin', 'metadata.pkl', 'terminology.json']:
                    continue
                
                # 检查文件年龄
                file_age = current_time - os.path.getctime(filepath)
                if file_age > days * 24 * 3600:  # 转换天数为秒
                    try:
                        os.remove(filepath)
                        print(f"Deleted old file: {filepath}")
                    except Exception as e:
                        print(f"Error deleting {filepath}: {e}")

import pandas as pd 