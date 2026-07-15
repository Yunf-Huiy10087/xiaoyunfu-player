// ============================================================
// 小云浮音乐耳机 - 主应用逻辑
// 依赖：player.js（播放器模块）
// ============================================================

// ============================================================
// 1. 全局状态
// ============================================================
var token = localStorage.getItem('token') || '';
var user = null;
var lastResults = [];
var currentPlayingIndex = -1;
var queueTimer = null;

// ============================================================
// 2. DOM 引用
// ============================================================
var $ = function(id) { return document.getElementById(id); };

// ============================================================
// 3. Toast 提示
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
// 暴露到全局，供 player.js 使用
window.toast = toast;

// ============================================================
// 4. 工具函数
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
// 5. API 封装
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
// 6. 认证
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
                
                toast('登录成功 ✅');
                loadPlaylists();
                loadQueue();
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
    if (token) {
        api('/api/v1/auth/logout', 'POST').catch(function() {});
    }
    token = '';
    user = null;
    localStorage.removeItem('token');
    stopQueuePolling();
    
    $('login-page').classList.remove('hidden');
    $('app').style.display = 'none';
    toast('已退出 👋');
}

// ============================================================
// 7. 面板切换
// ============================================================
function showPanel(n) {
    var panels = ['panel-1', 'panel-2', 'panel-3'];
    panels.forEach(function(id, i) {
        var el = $(id);
        if (el) el.classList.toggle('hidden', i !== n - 1);
    });
    
    var navs = document.querySelectorAll('.nav span');
    navs.forEach(function(el, i) {
        el.classList.toggle('active', i === n - 1);
    });
    
    if (n === 2) loadPlaylists();
    if (n === 3) loadQueue();
}

// ============================================================
// 8. 搜索
// ============================================================
function doSearch() {
    var kw = $('kw').value.trim();
    var src = $('src').value;
    
    if (!kw) {
        toast('请输入关键词～～(′Д`)', true);
        return;
    }
    
    $('rlist').innerHTML = '<div class="loading">🔍 搜索中...</div>';
    
    api('/api/v1/music/search', 'POST', {
        keyword: kw,
        source: src,
        limit: 30
    })
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
            '<div class="ri">' +
            '<div class="rt">' + (isPlaying ? '▶ ' : '') + esc(item.name) + '</div>' +
            '<div class="rs">' + esc(item.singer) + (item.album ? ' - ' + esc(item.album) : '') + '</div>' +
            '</div>' +
            '<span class="rd">' + fmt(item.duration) + '</span>' +
            '<span class="rts">' + item.source + '</span>' +
            '</div>';
    }
    $('rlist').innerHTML = h;
}

// ============================================================
// 9. 播放
// ============================================================
function playOne(idx) {
    var item = lastResults[idx];
    if (!item) return;
    
    // 如果是正在播放的歌曲，切换暂停/继续
    if (currentPlayingIndex === idx && window.player && window.player.isPlaying !== undefined) {
        window.player.toggle();
        return;
    }
    
    toast('🎵 正在请求: ' + item.name + '...');
    
    api('/api/v1/music/play', 'POST', {
        id: item.id,
        source: item.source
    })
    .then(function(r) {
        if (r.data) {
            if (r.data.queued) {
                toast('⏳ ' + (r.data.message || '已加入队列～～～o(≧口≦)o'));
                loadQueue();
                return;
            }
            if (r.data.url) {
                currentPlayingIndex = idx;
                if (window.player && window.player.play) {
                    window.player.play(r.data, r.data.url);
                    renderResults(lastResults);
                } else {
                    // 降级方案：直接播放
                    var audio = new Audio(r.data.url);
                    audio.play().catch(function(e) {
                        toast('播放失败～～(′Д`)', true);
                    });
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

// ============================================================
// 10. 歌单
// ============================================================
function loadPlaylists() {
    api('/api/v1/playlists', 'GET')
        .then(function(r) {
            var data = r.data || [];
            var h = '';
            if (data.length === 0) {
                h = '<div class="loading">暂无歌单</div>';
            } else {
                for (var i = 0; i < data.length; i++) {
                    var pl = data[i];
                    h += '<div class="pitem">' +
                        '<span class="pn">' + (pl.is_public ? '🌐' : '🔒') + ' ' + esc(pl.name) + 
                        '<span style="font-size:11px;color:#666;margin-left:8px">(' + (pl.song_count || 0) + '首)</span>' +
                        '</span>' +
                        '<button class="btn-sm" onclick="viewPlaylist(' + pl.id + ')">查看</button>' +
                        '</div>';
                }
            }
            $('pl-list').innerHTML = h;
        })
        .catch(function() {
            $('pl-list').innerHTML = '<div class="loading">加载失败～～(′Д`)</div>';
        });
}

function viewPlaylist(id) {
    toast('📁 歌单详情功能开发中');
}

// ============================================================
// 11. 队列
// ============================================================
function loadQueue() {
    api('/api/v1/queue', 'GET')
        .then(function(r) {
            var data = r.data || [];
            var h = '';
            if (data.length === 0) {
                h = '<div class="loading">队列为空 ✅</div>';
            } else {
                var statusMap = {
                    '排队中': '⏳',
                    '转码中': '🔄',
                    '完成': '✅',
                    '失败': '❌',
                    '已取消': '🚫'
                };
                for (var i = 0; i < data.length; i++) {
                    var q = data[i];
                    var icon = statusMap[q.status] || '⏳';
                    h += '<div class="pitem">' +
                        '<span>' + icon + ' ' + esc(q.name) + 
                        ' <span style="font-size:11px;color:#666">(' + q.status + ')</span></span>' +
                        '<span style="font-size:11px;color:#666">' + q.source + '</span>' +
                        '</div>';
                }
            }
            $('queue-list').innerHTML = h;
        })
        .catch(function() {
            $('queue-list').innerHTML = '<div class="loading">加载失败～～(′Д`)</div>';
        });
}

// ============================================================
// 12. 队列轮询
// ============================================================
function startQueuePolling() {
    stopQueuePolling();
    queueTimer = setInterval(function() {
        // 只在队列面板可见时刷新
        var panel = $('panel-3');
        if (panel && !panel.classList.contains('hidden')) {
            loadQueue();
        }
    }, 5000);
}

function stopQueuePolling() {
    if (queueTimer) {
        clearInterval(queueTimer);
        queueTimer = null;
    }
}

// ============================================================
// 13. 键盘事件
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    var kw = $('kw');
    var pass = $('l-pass');
    
    if (kw) {
        kw.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') doSearch();
        });
    }
    if (pass) {
        pass.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') doLogin();
        });
    }
    
    // 如果有 token，尝试自动恢复会话
    if (token) {
        api('/api/v1/auth/me', 'GET')
            .then(function(r) {
                if (r.code === 200 && r.data) {
                    user = r.data;
                    $('login-page').classList.add('hidden');
                    $('app').style.display = 'block';
                    $('uname').textContent = user.username || '管理员';
                    loadPlaylists();
                    loadQueue();
                    startQueuePolling();
                    toast('欢迎回来 👋');
                } else {
                    localStorage.removeItem('token');
                    token = '';
                }
            })
            .catch(function() {
                localStorage.removeItem('token');
                token = '';
            });
    }
});

// ============================================================
// 14. 暴露到全局
// ============================================================
window.app = {
    token: function() { return token; },
    user: function() { return user; },
    doLogin: doLogin,
    doLogout: doLogout,
    showPanel: showPanel,
    doSearch: doSearch,
    playOne: playOne,
    loadPlaylists: loadPlaylists,
    loadQueue: loadQueue,
    toast: toast
};

console.log('📱 小云浮音乐耳机 v5.0 已加载');
console.log('💡 默认账号: admin');
console.log('💡 默认密码: Hi-world');