document.addEventListener('DOMContentLoaded', function() {
    // 页面路径判断
    const path = window.location.pathname;
    
    // 根据页面路径执行相应的初始化
    if (path === '/upload' || path.includes('/upload')) {
        initUploadPage();
    } else if (path === '/pickup' || path.includes('/pickup')) {
        initPickupPage();
    } else if (path.includes('/manage/')) {
        initManagePage();
    }
    
    // 通用函数
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
      // 上传页面初始化
    function initUploadPage() {
        const fileInput = document.getElementById('file-upload');
        const fileList = document.getElementById('file-list');
        const uploadForm = document.getElementById('upload-form');
        const uploadProgress = document.getElementById('upload-progress');
        const progressFill = uploadProgress.querySelector('.progress-fill');
        const progressText = uploadProgress.querySelector('.progress-text');
        const uploadResult = document.getElementById('upload-result');
        const pickupCodeElement = document.getElementById('pickup-code');
        const managementUrlElement = document.getElementById('management-url');
        const copyButton = document.getElementById('copy-code');
        const resetButton = document.getElementById('reset-upload');
        const expiryValueInput = document.getElementById('expiry-value');
        const expiryUnitSelect = document.getElementById('expiry-unit');
        
        let selectedFiles = [];
        
        // 设置有效期输入限制
        if (expiryValueInput && expiryUnitSelect) {
            expiryUnitSelect.addEventListener('change', function() {
                const unit = this.value;
                if (unit === 'minutes') {
                    expiryValueInput.setAttribute('max', '1440'); // 最多24小时 = 1440分钟
                    if (parseInt(expiryValueInput.value) > 1440) {
                        expiryValueInput.value = 1440;
                    }
                } else if (unit === 'hours') {
                    expiryValueInput.setAttribute('max', '240'); // 最多10天 = 240小时
                    if (parseInt(expiryValueInput.value) > 240) {
                        expiryValueInput.value = 240;
                    }
                } else if (unit === 'days') {
                    expiryValueInput.setAttribute('max', '10'); // 最多10天
                    if (parseInt(expiryValueInput.value) > 10) {
                        expiryValueInput.value = 10;
                    }
                }
            });
            
            // 确保初始值在范围内
            expiryUnitSelect.dispatchEvent(new Event('change'));
        }
        
        // 文件选择事件
        fileInput.addEventListener('change', function(e) {
            const files = Array.from(e.target.files);
            selectedFiles = files;
            renderFileList();
        });
        
        // 渲染文件列表
        function renderFileList() {
            fileList.innerHTML = '';
            
            selectedFiles.forEach((file, index) => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                
                const fileName = document.createElement('div');
                fileName.className = 'file-name';
                fileName.textContent = file.name;
                
                const fileSize = document.createElement('div');
                fileSize.className = 'file-size';
                fileSize.textContent = formatFileSize(file.size);
                
                const removeButton = document.createElement('span');
                removeButton.className = 'file-remove';
                removeButton.textContent = '×';
                removeButton.addEventListener('click', () => {
                    selectedFiles.splice(index, 1);
                    renderFileList();
                });
                
                fileItem.appendChild(fileName);
                fileItem.appendChild(fileSize);
                fileItem.appendChild(removeButton);
                fileList.appendChild(fileItem);
            });
            
            // 如果没有选择文件，显示提示
            if (selectedFiles.length === 0) {
                const noFiles = document.createElement('div');
                noFiles.textContent = '未选择文件';
                noFiles.style.color = '#999';
                noFiles.style.textAlign = 'center';
                noFiles.style.padding = '10px';
                fileList.appendChild(noFiles);
            }
        }
        
        // 表单提交事件
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (selectedFiles.length === 0) {
                alert('请选择至少一个文件');
                return;
            }
            
            const formData = new FormData();
            
            // 添加文件
            selectedFiles.forEach(file => {
                formData.append('files[]', file);
            });
              // 添加其他表单数据
            formData.append('expiry_value', document.getElementById('expiry-value').value);
            formData.append('expiry_unit', document.getElementById('expiry-unit').value);
            formData.append('max_downloads', document.getElementById('max-downloads').value);
            
            // 显示上传进度条
            uploadForm.classList.add('hide');
            uploadProgress.classList.remove('hide');
            
            // 发送请求
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);
                    progressFill.style.width = percentComplete + '%';
                    progressText.textContent = '上传中 (' + percentComplete + '%)';
                }
            });
              xhr.addEventListener('load', function() {
                uploadProgress.classList.add('hide');
                  if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        
                        // 显示上传结果
                        pickupCodeElement.textContent = response.pickup_code;
                        
                        // 使用相对URL而非绝对URL
                        const managementUrl = `/manage/${response.file_group_id}`;
                        managementUrlElement.textContent = '管理链接';
                        managementUrlElement.href = managementUrl;
                        uploadResult.classList.remove('hide');
                    } catch (e) {
                        alert('解析响应错误: ' + e.message);
                        alert('上传成功，但返回数据解析失败。请刷新页面重试。');
                        uploadForm.classList.remove('hide');
                    }
                } else {
                    let errorMessage = '上传失败';
                    
                    try {
                        const response = JSON.parse(xhr.responseText);
                        if (response.error) {
                            errorMessage = response.error;
                        }                    } catch (e) {
                        // 如果服务器返回HTML，可能是由于服务器错误或413文件过大
                        if (xhr.status === 413) {
                            errorMessage = '文件太大，超出服务器限制';
                        } else if (xhr.responseText.includes('html')) {
                            errorMessage = '服务器错误，请联系管理员';
                        } else {
                            errorMessage = '解析响应错误: ' + e.message;
                        }
                    }
                    
                    alert(errorMessage);
                    uploadForm.classList.remove('hide');
                }
            });
            
            xhr.addEventListener('error', function() {
                uploadProgress.classList.add('hide');
                uploadForm.classList.remove('hide');
                alert('上传时发生网络错误');
            });
            
            xhr.open('POST', '/upload', true);
            xhr.send(formData);
        });
        
        // 复制取件码
        if (copyButton) {
            copyButton.addEventListener('click', function() {
                const code = pickupCodeElement.textContent;
                navigator.clipboard.writeText(code).then(() => {
                    copyButton.textContent = '已复制';
                    setTimeout(() => {
                        copyButton.textContent = '复制';
                    }, 2000);
                }).catch(err => {
                    alert('复制失败: ' + err);
                });
            });
        }
        
        // 重置上传表单
        if (resetButton) {
            resetButton.addEventListener('click', function() {
                uploadResult.classList.add('hide');
                uploadForm.classList.remove('hide');
                fileInput.value = '';
                selectedFiles = [];
                renderFileList();
            });
        }
        
        // 初始渲染文件列表
        renderFileList();
    }
    
    // 取件页面初始化
    function initPickupPage() {
        const pickupForm = document.getElementById('pickup-form');
        const pickupFormContainer = document.getElementById('pickup-form-container');
        const filesContainer = document.getElementById('files-container');
        const fileList = document.getElementById('file-list');
        const downloadAllButton = document.getElementById('download-all');
        const downloadProgress = document.getElementById('download-progress');
        let currentFiles = [];
        let fileGroupId = null;
        let downloadToken = null;
        
        // 表单提交事件
        if (pickupForm) {
            pickupForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const pickupCode = document.getElementById('pickup-code').value.trim();
                
                if (!pickupCode) {
                    alert('请输入取件码');
                    return;
                }
                
                const formData = new FormData();
                formData.append('pickup_code', pickupCode);
                
                // 发送请求
                fetch('/pickup', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        // 保存文件组ID和下载令牌
                        fileGroupId = data.file_group_id;
                        downloadToken = data.token;
                        currentFiles = data.files;
                        
                        // 显示文件列表
                        renderDownloadFileList();
                        pickupFormContainer.classList.add('hide');
                        filesContainer.classList.remove('hide');
                    } else {
                        alert(data.error || '取件码无效');
                    }                })
                .catch(error => {
                    if (error.message && error.message.includes('413')) {
                        alert('文件太大，超过服务器限制');
                    } else {
                        alert('请求失败: ' + error.message);
                    }
                });
            });
        }
        
        // 渲染下载文件列表
        function renderDownloadFileList() {
            fileList.innerHTML = '';
            
            currentFiles.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'download-file-item';
                
                const fileIcon = document.createElement('div');
                fileIcon.className = 'file-icon';
                fileIcon.textContent = '📄';
                
                const fileInfo = document.createElement('div');
                fileInfo.className = 'file-info';
                
                const fileTitle = document.createElement('div');
                fileTitle.className = 'file-title';
                fileTitle.textContent = file.name;
                
                const fileMeta = document.createElement('div');
                fileMeta.className = 'file-meta';
                fileMeta.textContent = formatFileSize(file.size);
                
                const downloadButton = document.createElement('button');
                downloadButton.className = 'btn small-btn download-btn';
                downloadButton.textContent = '下载';
                downloadButton.addEventListener('click', () => {
                    startDownload(file.name);
                });
                
                fileInfo.appendChild(fileTitle);
                fileInfo.appendChild(fileMeta);
                
                fileItem.appendChild(fileIcon);
                fileItem.appendChild(fileInfo);
                fileItem.appendChild(downloadButton);
                
                fileList.appendChild(fileItem);
            });
        }
          // 存储下载状态
        const downloadStatus = {};
        
        // 开始下载文件
        function startDownload(fileName) {
            if (!fileGroupId || !downloadToken) {
                alert('下载信息无效，请重新获取');
                return;
            }
              // 防止重复下载
            if (downloadStatus[fileName]) {
                alert(`文件 ${fileName} 正在下载中，请等待下载完成`);
                return;
            }
            
            // 记录下载状态
            downloadStatus[fileName] = true;
            
            const downloadUrl = `/download/${fileGroupId}/${fileName}?token=${downloadToken}`;
            
            // 创建下载链接
            const downloadLink = document.createElement('a');
            downloadLink.href = downloadUrl;
            downloadLink.setAttribute('download', fileName);
            downloadLink.setAttribute('target', '_blank');
            downloadLink.style.display = 'none';
            document.body.appendChild(downloadLink);
            
            // 点击链接开始下载
            downloadLink.click();
            
            // 延迟移除链接
            setTimeout(() => {
                document.body.removeChild(downloadLink);
                // 3分钟后才允许再次下载相同文件，防止重复请求
                setTimeout(() => {
                    downloadStatus[fileName] = false;
                }, 180000);
            }, 100);
        }
        
        // 下载全部文件
        if (downloadAllButton) {
            downloadAllButton.addEventListener('click', function() {
                if (currentFiles.length === 0) {
                    return;
                }
                
                // 依次下载所有文件
                let index = 0;
                downloadProgress.classList.remove('hide');
                
                function downloadNext() {
                    if (index >= currentFiles.length) {
                        // 全部下载完成
                        downloadProgress.classList.add('hide');
                        return;
                    }
                    
                    const file = currentFiles[index];
                    const progressPercent = Math.round((index / currentFiles.length) * 100);
                    downloadProgress.querySelector('.progress-fill').style.width = progressPercent + '%';
                    downloadProgress.querySelector('.progress-text').textContent = 
                        '下载中 (' + (index + 1) + '/' + currentFiles.length + ')';
                    
                    startDownload(file.name);
                    index++;
                    
                    // 延迟下载下一个文件，增加间隔到5秒，避免浏览器限制
                    setTimeout(downloadNext, 5000);
                }
                
                downloadNext();
            });
        }
    }
      // 管理页面初始化
    function initManagePage() {
        const deleteButton = document.getElementById('delete-files');
        const confirmModal = document.getElementById('confirm-modal');
        const confirmDeleteButton = document.getElementById('confirm-delete');
        const cancelDeleteButton = document.getElementById('cancel-delete');
        const refreshButton = document.getElementById('refresh-page');
        const autoRefreshCheckbox = document.getElementById('auto-refresh');
        const lastUpdateTime = document.getElementById('last-update-time');
        const refreshSpinner = document.getElementById('refresh-spinner');
        
        if (!deleteButton) return;
        
        let fileGroupId = deleteButton.dataset.id;
        let autoRefreshInterval = null;
        
        // 更新页面上次刷新时间
        function updateLastRefreshTime() {
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            lastUpdateTime.textContent = `${hours}:${minutes}:${seconds}`;
        }
        
        // 刷新页面数据
        function refreshPageData() {
            if (refreshSpinner) refreshSpinner.classList.remove('hide');
              fetch(`/api/file-group/${fileGroupId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.file_group) {
                        updatePageWithNewData(data.file_group);
                        updateLastRefreshTime();
                    } else {
                        alert('获取数据失败: ' + (data.error || '未知错误'));
                    }
                })
                .catch(error => {
                    alert('刷新数据出错: ' + error.message);
                })
                .finally(() => {
                    if (refreshSpinner) refreshSpinner.classList.add('hide');
                });
        }
        
        // 用新数据更新页面
        function updatePageWithNewData(fileGroup) {
            // 更新文件组信息
            document.querySelector('.info-value.code').textContent = fileGroup.pickup_code;
            
            // 更新下载次数
            const downloadCountElement = document.querySelectorAll('.info-value')[4];  // 第五个info-value元素
            if (downloadCountElement) {
                downloadCountElement.textContent = fileGroup.download_count;
            }
            
            // 更新下载历史
            const historyTableBody = document.querySelector('.history-panel .file-table tbody');
            if (historyTableBody) {
                // 清空现有表格内容
                historyTableBody.innerHTML = '';
                
                if (fileGroup.download_history && fileGroup.download_history.length > 0) {
                    fileGroup.download_history.forEach(download => {
                        const row = document.createElement('tr');
                        
                        const nameCell = document.createElement('td');
                        nameCell.textContent = download.filename;
                        
                        const timeCell = document.createElement('td');
                        timeCell.textContent = download.time.replace('T', ' ').substring(0, 16);
                        
                        const ipCell = document.createElement('td');
                        ipCell.textContent = download.ip;
                        
                        row.appendChild(nameCell);
                        row.appendChild(timeCell);
                        row.appendChild(ipCell);
                        
                        historyTableBody.appendChild(row);
                    });
                } else {
                    const row = document.createElement('tr');
                    const cell = document.createElement('td');
                    cell.textContent = '暂无下载记录';
                    cell.className = 'no-data';
                    cell.setAttribute('colspan', '3');
                    row.appendChild(cell);
                    historyTableBody.appendChild(row);
                }
            }
        }
        
        // 手动刷新按钮
        if (refreshButton) {
            refreshButton.addEventListener('click', function() {
                refreshPageData();
            });
        }
          // 自动刷新切换
        if (autoRefreshCheckbox) {
            autoRefreshCheckbox.addEventListener('change', function() {
                if (this.checked) {
                    // 开启自动刷新（增加到60秒一次，减少服务器负载）
                    autoRefreshInterval = setInterval(refreshPageData, 60000);
                    localStorage.setItem('autoRefresh', 'true');
                    
                    // 显示刷新状态
                    if (lastUpdateTime) {
                        lastUpdateTime.parentElement.innerHTML += ' <span class="refresh-note">(每分钟自动刷新)</span>';
                    }
                } else {
                    // 关闭自动刷新
                    if (autoRefreshInterval) {
                        clearInterval(autoRefreshInterval);
                        autoRefreshInterval = null;
                    }
                    localStorage.setItem('autoRefresh', 'false');
                    
                    // 移除刷新状态提示
                    const refreshNote = document.querySelector('.refresh-note');
                    if (refreshNote) {
                        refreshNote.remove();
                    }
                }
            });
            
            // 只在管理页面才开启自动刷新
            if (window.location.pathname.includes('/manage/') && localStorage.getItem('autoRefresh') === 'true') {
                autoRefreshCheckbox.checked = true;
                autoRefreshCheckbox.dispatchEvent(new Event('change'));
            } else {
                // 默认不开启自动刷新
                autoRefreshCheckbox.checked = false;
            }
        }
        
        // 初始化时更新刷新时间
        updateLastRefreshTime();
        
        // 显示确认删除模态框
        deleteButton.addEventListener('click', function() {
            confirmModal.classList.add('show');
        });
        
        // 取消删除
        if (cancelDeleteButton) {
            cancelDeleteButton.addEventListener('click', function() {
                confirmModal.classList.remove('show');
            });
        }
        
        // 确认删除
        if (confirmDeleteButton) {
            confirmDeleteButton.addEventListener('click', function() {
                // 发送删除请求
                fetch(`/api/delete/${fileGroupId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        window.location.href = '/'; // 删除成功后返回主页
                    } else {
                        alert(data.error || '删除失败');
                        confirmModal.classList.remove('show');
                    }
                })                .catch(error => {
                    alert('删除请求失败: ' + error.message);
                    confirmModal.classList.remove('show');
                });
            });
        }
    }
});
