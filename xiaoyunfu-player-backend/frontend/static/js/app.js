// ============================================================
// 小云浮音乐耳机 - 主应用逻辑
// ============================================================

var token = localStorage.getItem('token') || '';
var user = null;
var lastResults = [];
var currentPlayingIndex = -1;
var queueTimer = null;

// ============================================================
// DOM 引用
// ============================================================
function $(id) { return document.getElementById(id); }

// ============================================================
// Toast
// ============================================================
function toast(msg, isError) {
    var el = $('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'toast' + (isError ? ' err' : '');
    el.style.display = 'block';
    clearTimeout(el._timer);
    el._timer = setTimeout(function() { el.style.display = 'none'; }, 3500);
}
window.toast = toast;

// ============================================================
// 工具
// ============================================================
function esc(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function fmt(seconds) {
    if (!seconds || isNaN(seconds)) return '00:00';
    var m = Math.floor(seconds / 60);
    var s = Math.floor(seconds % 60);
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
}

// ============================================================
// API 封装（所有路径都带 /v1）
// ============================================================
function api(path, method, body) {
    var headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    var opts = { method: method || 'GET', headers: headers };
    if (body) opts.body = JSON.stringify(body);
    return fetch(path, opts).then(function(r) {
        return r.json().then(function(d) {
            if (!r.ok) {
                var e = new Error(d.detail || d.message || '请求失败');
                e.detail = d.detail || d.message || '';
                throw e;
            }
            return d;
        });
    });
}

// ============================================================
// 登录
// ============================================================
function doLogin() {
    var username = $('l-username').value.trim() || 'admin';
    var password = $('l-pass').value.trim();
    if (!password) {
        $('login-err').textContent = '请输入密码～～(′Д`)';
        return;
    }
    api('/api/v1/auth/login', 'POST', { username: username, password: password })
        .then(function(r) {
            if (r.code === 200) {
                token = r.data.token;
                user = r.data;
                localStorage.setItem('token', token);
                $('login-page').classList.add('hidden');
                $('app').style.display = 'block';
                $('uname').textContent = user.username || '管理员';
                // 显示/隐藏管理员标签
                if (user.is_admin) {
                    var tab = document.getElementById('admin-tab');
                    if (tab) tab.style.display = 'inline-block';
                }
                toast('登录成功 ✅');
                loadPlaylists();
                loadQueue();
                loadUploads();
                if (user.is_admin) loadUsers();
                startQueuePolling();
            } else {
                $('login-err').textContent = (r.message || '登录失败') + '～～(′Д`)';
            }
        })
        .catch(function(e) {
            $('login-err').textContent = (e.detail || e.message || '网络错误') + '～～(′Д`)';
        });
}

function doLogout() {
    if (token) { api('/api/v1/auth/logout', 'POST').catch(function() {}); }
    token = '';
    user = null;
    localStorage.removeItem('token');
    stopQueuePolling();
    $('login-page').classList.remove('hidden');
    $('app').style.display = 'none';
    toast('已退出 👋');
}

function changePwd() {
    var old = prompt('旧密码');
    var nw = prompt('新密码');
    if (!old || !nw) return;
    api('/api/v1/auth/change-pwd', 'POST', { old_password: old, new_password: nw })
        .then(function(r) { toast(r.message || '密码已修改'); })
        .catch(function(e) { toast('修改失败～～(′Д`)', true); });
}

// ============================================================
// 面板切换
// ============================================================
function showPanel(n) {
    var panels = ['panel-1', 'panel-2', 'panel-3', 'panel-4', 'panel-5'];
    panels.forEach(function(id, i) {
        var el = $(id);
        if (el) el.classList.toggle('hidden', i !== n - 1);
    });
    var navs = document.querySelectorAll('.nav span');
    navs.forEach(function(el, i) {
        el.classList.toggle('active', i === n - 1);
    });
    if (n === 2) loadPlaylists();
    if (n === 3) loadUploads();
    if (n === 4) loadQueue();
    if (n === 5 && user && user.is_admin) loadUsers();
}

// ============================================================
// 搜索
// ============================================================
function doSearch() {
    var kw = $('kw').value.trim();
    var src = $('src').value;
    if (!kw) { toast('请输入关键词～～(′Д`)', true); return; }
    $('rlist').innerHTML = '<div class="loading">🔍 搜索中...</div>';
    api('/api/v1/music/search', 'POST', { keyword: kw, source: src, limit: 30 })
        .then(function(r) {
            lastResults = r.data || [];
            renderResults(lastResults);
            toast('找到 ' + lastResults.length + ' 首');
        })
        .catch(function(e) {
            $('rlist').innerHTML = '<div class="loading">搜索失败～～(′Д`)</div>';
            toast('搜索失败～～(′Д`)', true);
        });
}

function renderResults(results) {
    if (!results || results.length === 0) {
        $('rlist').innerHTML = '<div class="loading">未找到结果</div>';
        return;
    }
    var h = '';
    for (var i = 0; i < results.length; i++) {
        var item = results[i];
        var isPlaying = (currentPlayingIndex === i);
        h += '<div class="ritem' + (isPlaying ? ' playing' : '') + '" onclick="playOne(' + i + ')">' +
            '<div class="ri"><div class="rt">' + (isPlaying ? '▶ ' : '') + esc(item.name) + '</div>' +
            '<div class="rs">' + esc(item.singer) + (item.album ? ' - ' + esc(item.album) : '') + '</div></div>' +
            '<span class="rd">' + fmt(item.duration) + '</span>' +
            '<span class="rts">' + item.source + '</span>' +
            '</div>';
    }
    $('rlist').innerHTML = h;
}

// ============================================================
// 播放
// ============================================================
function playOne(idx) {
    var item = lastResults[idx];
    if (!item) return;
    if (currentPlayingIndex === idx && window.player) {
        window.player.toggle();
        return;
    }
    toast('🎵 正在请求: ' + item.name + '...');
    api('/api/v1/music/play', 'POST', { id: item.id, source: item.source })
        .then(function(r) {
            if (r.data) {
                if (r.data.queued) {
                    toast('⏳ ' + (r.data.message || '已加入队列～～～o(≧口≦)o'));
                    loadQueue();
                    return;
                }
                if (r.data.url) {
                    currentPlayingIndex = idx;
                    if (window.player) {
                        window.player.play(r.data, r.data.url);
                        renderResults(lastResults);
                    }
                    toast('▶️ 正在播放: ' + r.data.name);
                    return;
                }
                toast('无法获取播放链接～～(′Д`)', true);
            }
        })
        .catch(function(e) {
            toast('播放失败: ' + (e.detail || e.message || '') + '～～(′Д`)', true);
        });
}

function prevSong() {
    if (currentPlayingIndex > 0) playOne(currentPlayingIndex - 1);
}
function nextSong() {
    if (currentPlayingIndex < lastResults.length - 1) playOne(currentPlayingIndex + 1);
}

// ============================================================
// 歌单
// ============================================================
function loadPlaylists() {
    api('/api/v1/playlists', 'GET')
        .then(function(r) {
            var data = r.data || [];
            var h = '';
            if (data.length === 0) { h = '<div class="loading">暂无歌单</div>'; }
            else {
                for (var i = 0; i < data.length; i++) {
                    var pl = data[i];
                    h += '<div class="pitem"><span class="pn">' + (pl.is_public ? '🌐' : '🔒') + ' ' + esc(pl.name) +
                        ' <span style="font-size:11px;color:#99a">(' + (pl.song_count || 0) + '首)</span></span>' +
                        '<button class="btn-sm" onclick="viewPlaylist(' + pl.id + ')">查看</button></div>';
                }
            }
            $('pl-list').innerHTML = h;
        })
        .catch(function() { $('pl-list').innerHTML = '<div class="loading">加载失败～～(′Д`)</div>'; });
}

function createPlaylist() {
    var name = $('pl-name').value.trim();
    var isPublic = $('pl-public').value === '1';
    if (!name) { toast('请输入歌单名称～～(′Д`)', true); return; }
    api('/api/v1/playlists', 'POST', { name: name, is_public: isPublic })
        .then(function(r) {
            toast(r.message || '创建成功');
            $('pl-name').value = '';
            loadPlaylists();
        })
        .catch(function(e) { toast('创建失败～～(′Д`)', true); });
}

function viewPlaylist(id) {
    toast('📁 歌单详情功能开发中');
}

// ============================================================
// 上传
// ============================================================
function uploadFile() {
    var file = $('up-file').files[0];
    if (!file) { toast('请选择文件～～(′Д`)', true); return; }
    var title = $('up-title').value.trim();
    var fd = new FormData();
    fd.append('file', file);
    fd.append('title', title);
    fetch('/api/v1/upload', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token },
        body: fd
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.code === 200) { toast('上传成功 ✅'); loadUploads(); }
        else { toast((d.detail || '上传失败') + '～～(′Д`)', true); }
    })
    .catch(function(e) { toast('上传失败～～(′Д`)', true); });
}

function uploadUrl() {
    var url = $('up-url').value.trim();
    var title = $('up-urltitle').value.trim();
    if (!url) { toast('请输入URL～～(′Д`)', true); return; }
    if (!title) { toast('请输入文件名～～(′Д`)', true); return; }
    api('/api/v1/upload-url', 'POST', { url: url, title: title })
        .then(function(r) {
            if (r.code === 200) { toast('上传成功 ✅'); loadUploads(); }
            else { toast((r.detail || '上传失败') + '～～(′Д`)', true); }
        })
        .catch(function(e) { toast('上传失败～～(′Д`)', true); });
}

function loadUploads() {
    api('/api/v1/uploads', 'GET')
        .then(function(r) {
            var data = r.data || [];
            var h = '';
            for (var i = 0; i < data.length; i++) {
                var f = data[i];
                h += '<div class="pitem"><span>' + esc(f.title) + '</span>' +
                    '<button class="btn-sm" onclick="playLocal(\'' + f.filepath + '\')">▶ 播放</button>' +
                    '<button class="btn-sm danger" onclick="delUp(\'' + f.filepath + '\')">删除</button></div>';
            }
            $('up-list').innerHTML = h || '<div class="loading">暂无文件</div>';
        })
        .catch(function(e) { $('up-list').innerHTML = '<div class="loading">加载失败～～(′Д`)</div>'; });
}

function playLocal(fname) {
    api('/api/v1/music/play', 'POST', { id: fname, source: 'local' })
        .then(function(r) {
            if (r.data && r.data.url) {
                if (window.player) window.player.play(r.data, r.data.url);
            }
        })
        .catch(function(e) { toast('播放失败～～(′Д`)', true); });
}

function delUp(fname) {
    if (!confirm('确定删除？')) return;
    fetch('/api/v1/uploads/' + fname, {
        method: 'DELETE',
        headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.code === 200) { toast('已删除'); loadUploads(); }
        else { toast('删除失败～～(′Д`)', true); }
    })
    .catch(function(e) { toast('删除失败～～(′Д`)', true); });
}

// ============================================================
// 队列
// ============================================================
function loadQueue() {
    api('/api/v1/queue', 'GET')
        .then(function(r) {
            var data = r.data || [];
            var h = '';
            if (data.length === 0) { h = '<div class="loading">队列为空 ✅</div>'; }
            else {
                var statusMap = { '排队中': '⏳', '转码中': '🔄', '完成': '✅', '失败': '❌', '已取消': '🚫' };
                for (var i = 0; i < data.length; i++) {
                    var q = data[i];
                    var icon = statusMap[q.status] || '⏳';
                    h += '<div class="pitem"><span>' + icon + ' ' + esc(q.name) +
                        ' <span style="font-size:11px;color:#99a">(' + q.status + ')</span></span>' +
                        '<span style="font-size:11px;color:#99a">' + q.source + '</span></div>';
                }
            }
            $('queue-list').innerHTML = h;
        })
        .catch(function() { $('queue-list').innerHTML = '<div class="loading">加载失败～～(′Д`)</div>'; });
}

function clearCompletedTasks() {
    if (!confirm('确定清空所有已完成的任务？')) return;
    api('/api/v1/queue/completed', 'DELETE')
        .then(function(r) { toast(r.message || '已清空'); loadQueue(); })
        .catch(function(e) { toast('清空失败～～(′Д`)', true); });
}

function startQueuePolling() {
    stopQueuePolling();
    queueTimer = setInterval(function() {
        var panel = $('panel-4');
        if (panel && !panel.classList.contains('hidden')) { loadQueue(); }
    }, 5000);
}

function stopQueuePolling() {
    if (queueTimer) { clearInterval(queueTimer); queueTimer = null; }
}

// ============================================================
// 管理员功能
// ============================================================
function loadUsers() {
    if (!user || !user.is_admin) return;
    api('/api/v1/admin/users', 'GET')
        .then(function(r) {
            var users = (r.data || []).filter(function(u) { return u.is_admin == 0; });
            var h = '';
            for (var i = 0; i < users.length; i++) {
                var u = users[i];
                h += '<div class="pitem"><span class="pn">' + esc(u.username) +
                    ' <span style="font-size:11px;color:#99a">' + u.created_at + '</span></span>' +
                    '<button class="btn-sm" onclick="resetUserPwd(' + u.id + ',\'' + esc(u.username) + '\')">重置密码</button>' +
                    '<button class="btn-sm danger" onclick="deleteUser(' + u.id + ')">删除</button></div>';
            }
            $('user-list').innerHTML = h || '<div class="loading">暂无普通用户</div>';
        })
        .catch(function() { $('user-list').innerHTML = '<div class="loading">加载失败～～(′Д`)</div>'; });
}

function resetUserPwd(id, name) {
    var newPw = prompt('为 ' + name + ' 设置新密码:');
    if (!newPw) return;
    api('/api/v1/admin/users/' + id + '/reset-password', 'POST', { new_password: newPw })
        .then(function(r) { toast(r.message || '密码已重置'); })
        .catch(function(e) { toast('重置失败～～(′Д`)', true); });
}

function deleteUser(id) {
    if (!confirm('确认删除该用户？')) return;
    api('/api/v1/admin/users/' + id, 'DELETE')
        .then(function(r) { toast(r.message || '已删除'); loadUsers(); })
        .catch(function(e) { toast('删除失败～～(′Д`)', true); });
}

function clearAllCache() {
    if (!user || !user.is_admin) { toast('仅管理员可操作～～(′Д`)', true); return; }
    if (!confirm('确定清空所有缓存？\n正在转码中的文件将被保留。')) return;
    api('/api/v1/admin/cache/all', 'DELETE')
        .then(function(r) { toast(r.message || '已清空缓存'); })
        .catch(function(e) { toast('清空失败～～(′Д`)', true); });
}

function runCacheCleanup() {
    if (!user || !user.is_admin) { toast('仅管理员可操作～～(′Д`)', true); return; }
    api('/api/v1/admin/cache/cleanup', 'POST')
        .then(function(r) { toast(r.message || '清理完成'); })
        .catch(function(e) { toast('清理失败～～(′Д`)', true); });
}

// ============================================================
// 键盘事件 & 自动登录
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    var kw = $('kw');
    if (kw) kw.addEventListener('keydown', function(e) { if (e.key === 'Enter') doSearch(); });
    var pass = $('l-pass');
    if (pass) pass.addEventListener('keydown', function(e) { if (e.key === 'Enter') doLogin(); });

    if (token) {
        api('/api/v1/auth/me', 'GET')
            .then(function(r) {
                if (r.code === 200 && r.data) {
                    user = r.data;
                    $('login-page').classList.add('hidden');
                    $('app').style.display = 'block';
                    $('uname').textContent = user.username || '管理员';
                    if (user.is_admin) {
                        var tab = document.getElementById('admin-tab');
                        if (tab) tab.style.display = 'inline-block';
                    }
                    loadPlaylists();
                    loadQueue();
                    loadUploads();
                    if (user.is_admin) loadUsers();
                    startQueuePolling();
                    toast('欢迎回来 👋');
                } else { localStorage.removeItem('token'); token = ''; }
            })
            .catch(function() { localStorage.removeItem('token'); token = ''; });
    }
});

console.log('🎧 小云浮音乐耳机 v5.0 已加载');
console.log('💡 默认账号: admin');
console.log('💡 默认密码: Hi-world');