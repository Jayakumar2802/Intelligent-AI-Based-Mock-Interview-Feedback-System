// avatar_lipsync.js - AI Avatar lip sync animations
let TTS_CONFIG = { rate: 0.95, pitch: 1.0, voice: null };

// Avatar animation control
const AvatarAnimator = {
    isSpeaking: false,
    blinkInterval: null,
    
    init() {
        this.startBlinking();
        console.log("🤖 Avatar animator initialized");
    },
    
    startBlinking() {
        // Random blinking (every 3-6 seconds)
        this.blinkInterval = setInterval(() => {
            if (!this.isSpeaking && Math.random() < 0.3) {
                this.blink();
            }
        }, 3000 + Math.random() * 3000);
    },
    
    blink() {
        const eyes = document.querySelectorAll('.eye-left, .eye-right');
        const closedEyes = document.querySelectorAll('.eye-left-closed, .eye-right-closed');
        
        // Close eyes
        eyes.forEach(eye => eye.style.display = 'none');
        closedEyes.forEach(eye => eye.style.display = 'block');
        
        // Open eyes after 200ms
        setTimeout(() => {
            eyes.forEach(eye => eye.style.display = 'block');
            closedEyes.forEach(eye => eye.style.display = 'none');
        }, 200);
    },
    
    startSpeaking() {
        this.isSpeaking = true;
        document.querySelectorAll('.avatar-speaking').forEach(el => {
            el.classList.add('active');
        });
        this.animateMouth();
    },
    
    stopSpeaking() {
        this.isSpeaking = false;
        document.querySelectorAll('.avatar-speaking').forEach(el => {
            el.classList.remove('active');
        });
        this.setMouthOpen(0);
        this.smile();
    },
    
    animateMouth() {
        if (!this.isSpeaking) return;
        
        const mouth = document.querySelector('.avatar-mouth');
        if (!mouth) return;
        
        // Random mouth movement while speaking
        const openAmount = 0.5 + Math.random() * 0.5;
        this.setMouthOpen(openAmount);
        
        setTimeout(() => this.animateMouth(), 100 + Math.random() * 150);
    },
    
    setMouthOpen(amount) {
        const mouth = document.querySelector('.avatar-mouth');
        if (!mouth) return;
        
        const mapped = 0.3 + Math.pow(amount, 0.8) * 0.7;
        mouth.style.transform = `scaleY(${mapped})`;
        mouth.style.opacity = (0.4 + amount * 0.6).toString();
    },
    
    smile() {
        const smile = document.querySelector('.smile');
        if (!smile) return;
        
        smile.style.transition = 'opacity 300ms ease-in-out';
        smile.style.opacity = '1';
        
        setTimeout(() => {
            smile.style.opacity = '0';
        }, 1000);
    }
};

// TTS and lip sync integration
async function speakAndLipSync(text, onProgress = null, onFinish = null) {
    // Start avatar animation
    AvatarAnimator.startSpeaking();
    
    // Small chance to blink before speaking
    if (Math.random() < 0.4) {
        setTimeout(() => AvatarAnimator.blink(), 200);
    }
    
    try {
        // Try server-side TTS first
        const resp = await fetch('/tts_synthesize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        
        if (resp.ok) {
            const j = await resp.json();
            if (j.ok && j.audio_base64) {
                await playBase64AudioAndAnimate(j.audio_base64, onProgress);
                if (onFinish) onFinish({ source: j.source || 'server' });
                AvatarAnimator.smile();
                return { source: j.source || 'server' };
            }
        }
    } catch (e) {
        console.warn('❌ Server TTS failed', e);
    }
    
    // Fallback to Web Speech API
    if ('speechSynthesis' in window) {
        return new Promise((resolve, reject) => {
            try {
                const utter = new SpeechSynthesisUtterance(text);
                utter.lang = 'en-US';
                utter.rate = TTS_CONFIG.rate || 0.95;
                utter.pitch = TTS_CONFIG.pitch || 1.0;
                
                if (TTS_CONFIG.voice) {
                    utter.voice = TTS_CONFIG.voice;
                }
                
                utter.onstart = () => {
                    if (onProgress) onProgress({ event: 'start' });
                };
                
                utter.onend = () => {
                    AvatarAnimator.stopSpeaking();
                    if (onProgress) onProgress({ event: 'end' });
                    setTimeout(() => AvatarAnimator.smile(), 150);
                    resolve({ source: 'webspeech' });
                };
                
                utter.onerror = (err) => {
                    AvatarAnimator.stopSpeaking();
                    reject(err);
                };
                
                speechSynthesis.speak(utter);
            } catch (err) {
                reject(err);
            }
        });
    }
    
    // No TTS available
    AvatarAnimator.stopSpeaking();
    if (onFinish) onFinish({ source: 'none' });
    return { source: 'none' };
}

// Audio playback with lip sync
async function playBase64AudioAndAnimate(base64, onProgress) {
    const binary = atob(base64);
    const len = binary.length;
    const buf = new Uint8Array(len);
    
    for (let i = 0; i < len; i++) {
        buf[i] = binary.charCodeAt(i);
    }
    
    const blob = new Blob([buf], { type: 'audio/mpeg' });
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const arrayBuffer = await blob.arrayBuffer();
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    
    const src = audioCtx.createBufferSource();
    src.buffer = audioBuffer;
    
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 1024;
    
    const gainNode = audioCtx.createGain();
    src.connect(gainNode);
    gainNode.connect(analyser);
    analyser.connect(audioCtx.destination);
    
    let playing = true;
    
    src.onended = () => {
        playing = false;
        AvatarAnimator.stopSpeaking();
        audioCtx.close();
        if (onProgress) onProgress({ event: 'end' });
    };
    
    if (onProgress) onProgress({ event: 'start' });
    
    src.start(0);
    
    // Real-time audio analysis for lip sync
    const data = new Uint8Array(analyser.frequencyBinCount);
    
    (function loop() {
        if (!playing) return;
        
        analyser.getByteFrequencyData(data);
        
        // Compute RMS-like volume
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
            let v = data[i] / 255;
            sum += v * v;
        }
        
        const rms = Math.sqrt(sum / data.length);
        const mouthOpen = Math.min(1, Math.max(0, (rms - 0.02) * 3.5));
        
        AvatarAnimator.setMouthOpen(mouthOpen);
        requestAnimationFrame(loop);
    })();
    
    return new Promise(resolve => {
        src.onended = () => {
            AvatarAnimator.stopSpeaking();
            resolve();
        };
    });
}

// Configuration functions
function setTtsRate(rate) {
    TTS_CONFIG.rate = rate;
}

function setTtsPitch(pitch) {
    TTS_CONFIG.pitch = pitch;
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    AvatarAnimator.init();
    
    // Set up voice rate control if available
    const voiceRate = document.getElementById('voiceRate');
    const voiceRateLabel = document.getElementById('voiceRateLabel');
    
    if (voiceRate && voiceRateLabel) {
        voiceRate.addEventListener('input', function() {
            voiceRateLabel.textContent = this.value;
            setTtsRate(parseFloat(this.value));
        });
    }
});

// Global exports
window.avatarTts = {
    speak: speakAndLipSync,
    setRate: setTtsRate,
    setPitch: setTtsPitch,
    blink: () => AvatarAnimator.blink(),
    smile: () => AvatarAnimator.smile()
};

window.AvatarAnimator = AvatarAnimator;