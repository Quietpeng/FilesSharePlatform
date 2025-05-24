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
        
        let selectedFiles = [];
        
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
            formData.append('expiry_days', document.getElementById('expiry-days').value);
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
                    const response = JSON.parse(xhr.responseText);
                    
                    // 显示上传结果
                    pickupCodeElement.textContent = response.pickup_code;
                    managementUrlElement.textContent = response.management_url;
                    managementUrlElement.href = response.management_url;
                    uploadResult.classList.remove('hide');
                } else {
                    let errorMessage = '上传失败';
                    
                    try {
                        const response = JSON.parse(xhr.responseText);
                        if (response.error) {
                            errorMessage = response.error;
                        }
                    } catch (e) {
                        console.error('解析响应错误', e);
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
                .then(response => response.json())
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
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('请求失败，请稍后重试');
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
        
        // 开始下载文件
        function startDownload(fileName) {
            if (!fileGroupId || !downloadToken) {
                alert('下载信息无效，请重新获取');
                return;
            }
            
            const downloadUrl = `/download/${fileGroupId}/${fileName}?token=${downloadToken}`;
            window.open(downloadUrl, '_blank');
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
                    
                    // 延迟下载下一个文件
                    setTimeout(downloadNext, 1000);
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
        
        if (!deleteButton) return;
        
        let fileGroupId = deleteButton.dataset.id;
        
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
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('请求失败，请稍后重试');
                    confirmModal.classList.remove('show');
                });
            });
        }
    }
});
