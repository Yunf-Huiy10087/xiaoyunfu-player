// ============================================================
// 小云浮音乐耳机 - 播放器模块
// ============================================================

var audio = null;
var currentSong = null;
var lyricLines = [];
var isPlaying = false;

// ============================================================
// 播放控制
// ============================================================

function playSong(songData, url) {
    if (audio) { audio.pause(); audio = null; }
    currentSong = songData;
    audio = new Audio(url);
    audio.volume = 0.8;

    audio.onplay = function() {
        isPlaying = true;
        document.getElementById('btnplay').textContent = '⏸';
        document.getElementById('pcover').classList.add('playing');
        document.getElementById('disc').classList.add('playing');
        document.getElementById('pname').textContent = songData.name || '未知歌曲';
        document.getElementById('part').textContent = songData.singer || '未知歌手';

        var coverEl = document.getElementById('pcover');
        if (songData.cover_url) {
            coverEl.innerHTML = '<img src="' + songData.cover_url + '" style="width:100%;height:100%;object-fit:cover;">';
        } else {
            coverEl.innerHTML = '<img src="/static/img/Yunf_Huiy10087_Transparent.webp" style="width:100%;height:100%;object-fit:cover;">';
        }

        updateInfoPanel(songData);
    };

    audio.onpause = function() {
        isPlaying = false;
        document.getElementById('btnplay').textContent = '▶';
        document.getElementById('pcover').classList.remove('playing');
        document.getElementById('disc').classList.remove('playing');
    };

    audio.ontimeupdate = function() {
        if (!audio.duration || isNaN(audio.duration)) return;
        var progress = (audio.currentTime / audio.duration) * 100;
        document.getElementById('pseek').value = progress;
        document.getElementById('ptime').textContent = formatTime(audio.currentTime);
        document.getElementById('pdura').textContent = formatTime(audio.duration);
        updateLyric(audio.currentTime);
    };

    audio.onended = function() {
        isPlaying = false;
        document.getElementById('btnplay').textContent = '▶';
        document.getElementById('pcover').classList.remove('playing');
        document.getElementById('disc').classList.remove('playing');
    };

    if (songData.lyric) parseLyric(songData.lyric);
    audio.play().catch(function(e) {
        window.toast && window.toast('播放失败～～(′Д`)', true);
    });
}

function togglePlay() {
    if (!audio) return;
    audio.paused ? audio.play() : audio.pause();
}

function seek(value) {
    if (!audio || !audio.duration) return;
    audio.currentTime = (value / 100) * audio.duration;
}

function setVolume(value) {
    if (audio) audio.volume = value / 100;
}

function setSpeed(speed) {
    if (audio) audio.playbackRate = speed;
    var btn = document.querySelector('.pspeed .btn-sm');
    if (btn) btn.textContent = '▶' + speed + 'x';
    document.getElementById('spd-menu').classList.add('hidden');
}

// ============================================================
// 歌词
// ============================================================

function parseLyric(lrc) {
    lyricLines = [];
    if (!lrc) return;
    var lines = lrc.split('\n');
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        var m = line.match(/\[(\d+):(\d+)\.(\d+)\](.*)/);
        if (m) {
            var time = parseInt(m[1]) * 60 + parseInt(m[2]) + parseInt(m[3]) / 1000;
            var text = (m[4] || '').trim() || '...';
            lyricLines.push({ time: time, text: text });
        }
    }
    lyricLines.sort(function(a, b) { return a.time - b.time; });
}

function updateLyric(currentTime) {
    var el = document.getElementById('lyric-float-text');
    if (!el) return;
    if (lyricLines.length === 0) {
        el.innerHTML = '纯音乐 / 暂无歌词<br>o(≧口≦)o';
        return;
    }
    var activeIdx = 0;
    for (var i = 0; i < lyricLines.length; i++) {
        if (lyricLines[i].time <= currentTime) activeIdx = i;
    }
    var h = '';
    for (var i = 0; i < lyricLines.length; i++) {
        h += '<div class="' + (i === activeIdx ? 'la' : 'li') + '">' + lyricLines[i].text + '</div>';
    }
    el.innerHTML = h;
}

function toggleLyric() {
    var el = document.getElementById('lyric-float');
    el.classList.toggle('show');
    if (el.classList.contains('show') && audio) {
        updateLyric(audio.currentTime || 0);
    }
}

// ============================================================
// 信息面板
// ============================================================

function toggleInfo() {
    document.getElementById('info-panel').classList.toggle('show');
}

function updateInfoPanel(songData) {
    var el = document.getElementById('info-content');
    if (!el) return;
    el.innerHTML = '<b>' + esc(songData.name || '未知') + '</b><br>' +
        '歌手: ' + (songData.singer || '未知') + '<br>' +
        '来源: ' + (songData.source || '未知') + '<br>' +
        '时长: ' + formatTime(songData.duration || 0) +
        (songData.album ? '<br>专辑: ' + songData.album : '');
}

// ============================================================
// 工具函数
// ============================================================

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '00:00';
    var m = Math.floor(seconds / 60);
    var s = Math.floor(seconds % 60);
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
}

function esc(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ============================================================
// 暴露到全局
// ============================================================

window.player = {
    play: playSong,
    toggle: togglePlay,
    seek: seek,
    volume: setVolume,
    speed: setSpeed,
    toggleLyric: toggleLyric,
    toggleInfo: toggleInfo,
    isPlaying: function() { return isPlaying; }
};

console.log('🎵 播放器模块已加载');