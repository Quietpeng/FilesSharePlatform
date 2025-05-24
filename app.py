import os
import json
import uuid
import shutil
from flask import Flask, request, render_template, send_from_directory, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
import datetime
import hashlib
import random
import string
import sys

# 解决大文件上传413错误
import werkzeug.formparser

# 加载配置文件
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    print("已加载配置文件")
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"配置文件错误: {e}")
    print("使用默认配置")
    config = {
        "server": {"host": "0.0.0.0", "port": 5000, "debug": True},
        "file_limits": {"max_file_size_mb": 16384, "max_group_size_mb": 32768, "max_files_per_group": 100, "total_storage_limit_gb": 100},
        "time_limits": {"min_expiry_minutes": 1, "max_expiry_days": 10, "default_expiry_minutes": 10},
        "pickup_code": {"length_min": 6, "length_max": 10, "default_length": 6},
        "security": {
            "allowed_extensions": ["txt", "pdf", "png", "jpg", "jpeg", "gif", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "rar", "7z", "mp3", "mp4", "avi", "mov"],
            "forbidden_extensions": ["php", "exe", "bat", "cmd", "sh", "js", "vbs", "py"]
        }
    }

# 修改Werkzeug库的表单解析器的默认文件大小限制(默认为64MB)
max_size_bytes = config["file_limits"]["max_file_size_mb"] * 1024 * 1024
werkzeug.formparser.default_max_form_memory_size = max_size_bytes

app = Flask(__name__)

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files')
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file_data.json')
ALLOWED_EXTENSIONS = set(config["security"]["allowed_extensions"])
FORBIDDEN_EXTENSIONS = set(config["security"]["forbidden_extensions"])
MAX_CONTENT_LENGTH = max_size_bytes

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 工具函数
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"file_groups": {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext not in FORBIDDEN_EXTENSIONS and (ext in ALLOWED_EXTENSIONS or '*' in ALLOWED_EXTENSIONS)

def generate_pickup_code(length=None):
    # 从配置获取取件码长度
    if length is None:
        length = config["pickup_code"]["default_length"]
    # 生成数字+字母的取件码
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def check_file_for_virus(file_path):
    """
    检查文件是否存在安全风险
    1. 检查文件扩展名
    2. 对特定类型文件进行内容检查
    3. 检查隐藏的扩展名（如 file.php.jpg）
    """
    filename = os.path.basename(file_path)
    
    # 1. 检查文件扩展名
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in FORBIDDEN_EXTENSIONS:
        return False
    
    # 2. 检查文件名是否包含多个扩展名，如 file.php.jpg
    name_parts = filename.split('.')
    if len(name_parts) > 2:
        suspicious_exts = [part.lower() for part in name_parts[1:-1]]
        if any(ext in FORBIDDEN_EXTENSIONS for ext in suspicious_exts):
            return False
    
    # 3. 对特定类型文件进行内容检查
    # 检查图片文件是否包含PHP代码
    if ext in ['jpg', 'jpeg', 'png', 'gif']:
        try:
            with open(file_path, 'rb') as f:
                content = f.read(4096)  # 读取文件头部
                # 检查是否包含PHP标签
                if b'<?php' in content or b'<?=' in content:
                    return False
        except Exception:
            pass  # 如果读取失败，继续执行
            
    # 4. 检查ZIP文件内容
    if ext in ['zip']:
        import zipfile
        try:
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path) as zf:
                    for info in zf.infolist():
                        if any(info.filename.lower().endswith('.' + forbidden_ext) 
                               for forbidden_ext in FORBIDDEN_EXTENSIONS):
                            return False
        except Exception:
            pass  # 如果读取失败，继续执行
    
    return True

def create_download_token(file_group_id):
    # 创建下载令牌
    token = str(uuid.uuid4())
    data = load_data()
    if file_group_id in data["file_groups"]:
        data["file_groups"][file_group_id]["download_token"] = token
        data["file_groups"][file_group_id]["token_created"] = datetime.datetime.now().isoformat()
        save_data(data)
    return token

def validate_token(file_group_id, token):
    # 验证下载令牌
    data = load_data()
    if file_group_id in data["file_groups"]:
        if data["file_groups"][file_group_id].get("download_token") == token:
            return True
    return False

def get_total_storage_usage():
    # 计算当前储存使用量
    total_bytes = 0
    for root, dirs, files in os.walk(UPLOAD_FOLDER):
        for file in files:
            file_path = os.path.join(root, file)
            total_bytes += os.path.getsize(file_path)
    return total_bytes

def check_storage_limit():
    # 检查是否超出总存储限制
    max_bytes = config["file_limits"]["total_storage_limit_gb"] * 1024 * 1024 * 1024
    current_bytes = get_total_storage_usage()
    return current_bytes <= max_bytes, current_bytes, max_bytes

def clean_expired_files():
    data = load_data()
    now = datetime.datetime.now()
    to_delete = []
    
    for file_id, info in data["file_groups"].items():
        # 检查有效期
        if "expiry_date" in info:
            expiry_date = datetime.datetime.fromisoformat(info["expiry_date"])
            if now > expiry_date:
                to_delete.append(file_id)
                continue
                
    # 检查下载次数
        if "max_downloads" in info and info["max_downloads"] is not None and info.get("download_count", 0) >= info["max_downloads"]:
            to_delete.append(file_id)
    
    # 删除过期文件
    for file_id in to_delete:
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        if file_id in data["file_groups"]:
            del data["file_groups"][file_id]
    
    save_data(data)

def validate_expiry_settings(expiry_unit, expiry_value):
    # 验证有效期设置是否在允许范围内
    min_minutes = config["time_limits"]["min_expiry_minutes"]
    max_days = config["time_limits"]["max_expiry_days"]
    
    if expiry_unit == 'minutes':
        return max(min_minutes, min(expiry_value, max_days * 24 * 60))
    elif expiry_unit == 'hours':
        return max(min_minutes // 60, min(expiry_value, max_days * 24))
    elif expiry_unit == 'days':
        return max(1, min(expiry_value, max_days))
    else:
        return config["time_limits"]["default_expiry_minutes"]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        # 传递配置项到模板
        return render_template('upload.html', config=config)
        
    if request.method == 'POST':
        # 检查是否有文件
        if 'files[]' not in request.files:
            return jsonify({'error': '没有文件被上传'}), 400
            
        files = request.files.getlist('files[]')
        if not files or files[0].filename == '':
            return jsonify({'error': '没有选择文件'}), 400
            
        # 检查文件数量限制
        if len(files) > config["file_limits"]["max_files_per_group"]:
            return jsonify({'error': f'一次最多只能上传{config["file_limits"]["max_files_per_group"]}个文件'}), 400
            
        # 检查存储空间
        has_space, current_size, max_size = check_storage_limit()
        if not has_space:
            return jsonify({'error': f'服务器存储空间已满 ({current_size/(1024**3):.2f}GB/{max_size/(1024**3):.2f}GB)'}), 507
            
        # 获取有效期和最大下载次数
        expiry_unit = request.form.get('expiry_unit', 'minutes')
        expiry_value = int(request.form.get('expiry_value', config["time_limits"]["default_expiry_minutes"]))
        # 验证有效期设置
        expiry_value = validate_expiry_settings(expiry_unit, expiry_value)
        
        max_downloads = int(request.form.get('max_downloads', 0))
        
        # 创建文件组ID和取件码
        file_group_id = str(uuid.uuid4())
        pickup_code = generate_pickup_code()
        
        # 确保目录存在
        group_folder = os.path.join(app.config['UPLOAD_FOLDER'], file_group_id)
        os.makedirs(group_folder, exist_ok=True)
        
        # 处理文件上传
        file_info = []
        total_group_size = 0
        
        for file in files:
            if file and allowed_file(file.filename):                
                original_filename = file.filename
                # 生成一个安全的文件名用于存储
                safe_filename = secure_filename(original_filename)
                # 如果安全文件名为空（例如只包含非ASCII字符），使用一个哈希值作为文件名
                if not safe_filename:
                    name_hash = hashlib.md5(original_filename.encode('utf-8')).hexdigest()
                    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
                    safe_filename = f"{name_hash}.{ext}" if ext else name_hash
                
                file_path = os.path.join(group_folder, safe_filename)
                file.save(file_path)
                
                # 检查病毒
                if not check_file_for_virus(file_path):
                    shutil.rmtree(group_folder)  # 删除整个文件夹
                    return jsonify({'error': '发现潜在危险文件，上传已取消'}), 400
                
                file_size = os.path.getsize(file_path)
                
                # 检查单个文件大小
                if file_size > MAX_CONTENT_LENGTH:
                    shutil.rmtree(group_folder)
                    return jsonify({'error': f'文件 {original_filename} 过大，超过{config["file_limits"]["max_file_size_mb"]}MB限制'}), 413
                    
                total_group_size += file_size
                
                # 检查文件组总大小
                if total_group_size > config["file_limits"]["max_group_size_mb"] * 1024 * 1024:
                    shutil.rmtree(group_folder)
                    return jsonify({'error': f'文件组总大小超过{config["file_limits"]["max_group_size_mb"]}MB限制'}), 413
                
                file_info.append({
                    'name': original_filename,  # 保存原始文件名用于显示
                    'safe_name': safe_filename,  # 保存安全文件名用于存储
                    'size': file_size,
                    'upload_time': datetime.datetime.now().isoformat()
                })
            else:
                shutil.rmtree(group_folder)
                return jsonify({'error': f'不支持的文件类型或包含潜在危险文件'}), 400
        
        # 保存文件组信息
        data = load_data()
        expiry_date = None
        if expiry_value > 0:
            # 根据单位设置过期时间
            if expiry_unit == 'minutes':
                expiry_date = (datetime.datetime.now() + datetime.timedelta(minutes=expiry_value)).isoformat()
            elif expiry_unit == 'hours':
                expiry_date = (datetime.datetime.now() + datetime.timedelta(hours=expiry_value)).isoformat()
            elif expiry_unit == 'days':
                expiry_date = (datetime.datetime.now() + datetime.timedelta(days=expiry_value)).isoformat()
            
        data["file_groups"][file_group_id] = {
            'pickup_code': pickup_code,
            'files': file_info,
            'created_at': datetime.datetime.now().isoformat(),
            'expiry_date': expiry_date,
            'max_downloads': max_downloads if max_downloads > 0 else None,
            'download_count': 0,
            'download_history': [],
            'total_size': total_group_size
        }
        save_data(data)
          # 返回上传成功信息
        return jsonify({
            'success': True,
            'file_group_id': file_group_id,
            'pickup_code': pickup_code
        })

@app.route('/pickup', methods=['GET', 'POST'])
def pickup_file():
    if request.method == 'GET':
        return render_template('pickup.html')
        
    if request.method == 'POST':
        pickup_code = request.form.get('pickup_code')
        if not pickup_code:
            return jsonify({'error': '请输入取件码'}), 400
            
        # 清理过期文件
        clean_expired_files()
            
        # 查找对应文件组
        data = load_data()
        file_group_id = None
        
        for f_id, info in data["file_groups"].items():
            if info.get('pickup_code') == pickup_code:
                file_group_id = f_id
                break
        
        if not file_group_id:
            return jsonify({'error': '取件码无效或已过期'}), 404
            
        # 创建下载令牌
        token = create_download_token(file_group_id)
        
        # 返回文件列表和下载令牌
        file_info = data["file_groups"][file_group_id]['files']
        return jsonify({
            'success': True,
            'file_group_id': file_group_id,
            'token': token,
            'files': file_info
        })

@app.route('/download/<file_group_id>/<filename>')
def download_file(file_group_id, filename):
    token = request.args.get('token')
    if not token or not validate_token(file_group_id, token):
        return jsonify({'error': '无效或已过期的下载链接'}), 403
        
    # 加载文件数据
    data = load_data()
    if file_group_id not in data["file_groups"]:
        return jsonify({'error': '找不到请求的文件'}), 404
        
    # 查找对应的安全文件名
    safe_filename = None
    original_filename = filename
    file_size = 0
    
    for file in data["file_groups"][file_group_id]['files']:
        if file['name'] == filename:
            # 如果是旧数据可能没有safe_name字段，此时name和safe_name相同
            safe_filename = file.get('safe_name', file['name'])
            file_size = file.get('size', 0)
            break
            
    if not safe_filename:
        return jsonify({'error': '找不到请求的文件'}), 404
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_group_id)
    full_path = os.path.join(file_path, safe_filename)
    
    # 检查文件是否存在
    if not os.path.exists(full_path):
        return jsonify({'error': '文件不存在'}), 404
    
    # 获取真实文件大小
    real_file_size = os.path.getsize(full_path)
    
    # 处理范围请求（断点续传）
    range_header = request.headers.get('Range', None)
    
    # 如果这是第一次请求（不是断点续传），则记录下载信息
    if not range_header:
        # 避免重复记录下载统计，使用请求UA和IP作为简单的客户端标识
        client_id = f"{request.remote_addr}-{request.user_agent.string}"
        # 检查是否在最近5分钟内已经记录过此客户端的下载
        record_download = True
        
        if 'recent_downloads' not in data["file_groups"][file_group_id]:
            data["file_groups"][file_group_id]['recent_downloads'] = {}
        
        if client_id in data["file_groups"][file_group_id]['recent_downloads']:
            last_download = datetime.datetime.fromisoformat(data["file_groups"][file_group_id]['recent_downloads'][client_id])
            time_diff = (datetime.datetime.now() - last_download).total_seconds()
            if time_diff < 300:  # 5分钟内不重复记录
                record_download = False
        
        if record_download:
            download_info = {
                'filename': original_filename,
                'time': datetime.datetime.now().isoformat(),
                'ip': request.remote_addr
            }
            data["file_groups"][file_group_id]['download_history'].append(download_info)
            data["file_groups"][file_group_id]['download_count'] = data["file_groups"][file_group_id].get('download_count', 0) + 1
            data["file_groups"][file_group_id]['recent_downloads'][client_id] = datetime.datetime.now().isoformat()
            save_data(data)
    
    # 使用Flask的send_from_directory，它会自动处理断点续传请求
    response = send_from_directory(
        file_path, 
        safe_filename, 
        as_attachment=True, 
        download_name=original_filename
    )
    
    # 启用断点续传，添加必要的头信息
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Cache-Control'] = 'no-cache'
    
    return response

@app.route('/manage/<file_group_id>')
def manage_files(file_group_id):
    data = load_data()
    if file_group_id not in data["file_groups"]:
        return render_template('error.html', message='找不到指定的文件组')
        
    file_group = data["file_groups"][file_group_id]
    return render_template('manage.html', file_group=file_group, file_group_id=file_group_id)

@app.route('/api/delete/<file_group_id>', methods=['POST'])
def delete_file_group(file_group_id):
    data = load_data()
    if file_group_id not in data["file_groups"]:
        return jsonify({'error': '找不到指定的文件组'}), 404
        
    # 删除文件夹
    folder_path = os.path.join(app.config['UPLOAD_FOLDER'], file_group_id)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        
    # 删除数据记录
    del data["file_groups"][file_group_id]
    save_data(data)
    
    return jsonify({'success': True})

@app.route('/static/css/style.css')
def serve_css():
    return send_from_directory('static/css', 'style.css')

@app.route('/static/js/script.js')
def serve_js():
    return send_from_directory('static/js', 'script.js')

@app.route('/api/system-info')
def system_info():
    # 获取系统信息的API
    has_space, current_size, max_size = check_storage_limit()
    return jsonify({
        'storage': {
            'used_bytes': current_size,
            'used_gb': current_size / (1024**3),
            'max_bytes': max_size,
            'max_gb': max_size / (1024**3),
            'percent_used': (current_size / max_size) * 100 if max_size > 0 else 0
        },
        'file_limits': config["file_limits"],
        'time_limits': config["time_limits"]
    })

@app.route('/api/file-group/<file_group_id>')
def get_file_group_info(file_group_id):
    # 清理过期文件
    clean_expired_files()
    
    # 获取文件组信息的API
    data = load_data()
    if file_group_id not in data["file_groups"]:
        return jsonify({'error': '找不到指定的文件组'}), 404
        
    return jsonify({
        'success': True,
        'file_group': data["file_groups"][file_group_id]
    })

def clean_all_files():
    """清理所有文件和数据"""
    data = load_data()
    
    # 删除所有文件
    if os.path.exists(UPLOAD_FOLDER):
        for item in os.listdir(UPLOAD_FOLDER):
            item_path = os.path.join(UPLOAD_FOLDER, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
    
    # 清空数据文件
    save_data({"file_groups": {}})
    print("已清理所有文件和数据")

def handle_shutdown_signal(signum, frame):
    """处理关闭信号"""
    print("\n正在关闭服务...", flush=True)
    
    # 判断是否需要清理文件
    if os.environ.get('CLEAN_ON_EXIT', 'false').lower() == 'true':
        print("清理所有文件和数据...", flush=True)
        clean_all_files()
    else:
        print("保留所有文件和数据", flush=True)
    
    print("服务已安全关闭", flush=True)
    sys.exit(0)

if __name__ == '__main__':
    # 处理命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='文件共享平台')
    parser.add_argument('--clean', action='store_true', help='启动时清理所有文件')
    parser.add_argument('--clean-on-exit', action='store_true', help='退出时清理所有文件')
    args = parser.parse_args()
    
    # 设置环境变量
    if args.clean_on_exit:
        os.environ['CLEAN_ON_EXIT'] = 'true'
    
    # 注册信号处理器
    import signal
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    
    # 确保文件夹存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # 确保数据文件存在
    if not os.path.exists(DATA_FILE):
        save_data({"file_groups": {}})
    
    # 如果需要，清理所有文件
    if args.clean:
        clean_all_files()
    else:
        # 只清理过期文件
        clean_expired_files()
    
    # 从配置读取服务器设置
    host = config["server"]["host"]
    port = config["server"]["port"]
    debug = config["server"]["debug"]
    
    print(f"文件共享平台启动中... http://{host}:{port}")
    print(f"最大文件大小: {config['file_limits']['max_file_size_mb']}MB")
    print(f"最大文件组大小: {config['file_limits']['max_group_size_mb']}MB")
    print(f"配置存储空间: {config['file_limits']['total_storage_limit_gb']}GB")
    print(f"退出时清理文件: {'启用' if args.clean_on_exit else '禁用'}")
    
    try:
        app.run(debug=debug, host=host, port=port)
    except KeyboardInterrupt:
        print("\n检测到键盘中断，正在关闭服务...")
        if os.environ.get('CLEAN_ON_EXIT', 'false').lower() == 'true':
            clean_all_files()
