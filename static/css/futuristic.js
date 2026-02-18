// futuristic.js - Advanced interview logic with all features
let GLOBAL_RECORDER = null;
let GLOBAL_STREAM = null;
let currentRecordingChunks = [];
let currentQuestionInfo = null;
let silenceTimeout = null;
let audioContext = null;
let analyser = null;
let isUserSpeaking = false;
let lastVoiceTime = 0;
const SILENCE_MS = 10000;

// Interview state management
let interviewState = {
    isActive: false,
    currentQuestionIndex: 0,
    questions: [],
    role: '',
    startTime: null,
    answers: []
};

document.addEventListener("DOMContentLoaded", function(){
    console.log("🚀 Interview AI Frontend Loaded");
    
    // Role selection
    document.querySelectorAll(".role-item").forEach(function(item){
        item.addEventListener("click", function(){
            document.querySelectorAll(".role-item").forEach(i=>i.classList.remove("selected"));
            item.classList.add("selected");
            const role = item.dataset.role;
            loadRole(role);
        });
    });

    // Initialize first role
    const firstRole = document.querySelector(".role-item");
    if(firstRole){
        firstRole.classList.add("selected");
        loadRole(firstRole.dataset.role);
    }
});

// Load questions for role
async function loadRole(role){
    const qContainer = document.querySelector("#questions-container");
    if(!qContainer) return;
    
    qContainer.innerHTML = "<div class='muted small'>🔄 Loading questions...</div>";
    
    try{
        const response = await fetch(`/questions/${encodeURIComponent(role)}`);
        const data = await response.json();
        
        if(data.length === 0){
            qContainer.innerHTML = "<div class='muted small'>❌ No questions found for this role</div>";
            return;
        }

        // Build question cards
        qContainer.innerHTML = "";
        data.forEach((q,i)=>{
            const div = document.createElement("div");
            div.className = `question-card ${i===0?"visible":"hidden"}`;
            div.dataset.index = i;
            div.dataset.career = role;
            div.innerHTML = `
                <div class="question">
                    <strong>Q${i+1}:</strong> ${escapeHtml(q.question || '')}
                </div>
                <div class="small muted">🎤 Recording starts automatically after question</div>
                <div style="margin-top:8px">
                    <button class="button stop-record" style="background:var(--primary);color:white;border:none;padding:8px 12px;border-radius:6px;cursor:pointer">
                        ✅ Stop & Next Question
                    </button>
                    <span class="record-status muted small" style="margin-left:12px">⏸️ Ready</span>
                </div>
                <div class="silence-timer muted small" style="margin-top:8px">
                    ⏰ Next in: <span class="timer-value">${SILENCE_MS/1000}</span>s
                </div>
            `;
            qContainer.appendChild(div);
        });

        // Attach event handlers
        document.querySelectorAll(".stop-record").forEach(btn=>{
            btn.addEventListener("click", function(e){
                stopAndSendRecording();
                const nextBtn = document.querySelector("#next-question-btn");
                if(nextBtn) nextBtn.click();
            });
        });

        // Start first question
        const first = qContainer.querySelector(".question-card.visible");
        if(first) onQuestionVisible(first);
        
    }catch(err){
        console.error("❌ Failed to load questions:", err);
        qContainer.innerHTML = "<div class='muted small'>❌ Failed to load questions</div>";
    }
}

function onQuestionVisible(card){
    document.querySelectorAll(".question-card").forEach(c=>c.classList.remove("active"));
    card.classList.add("active");
    
    const career = card.dataset.career || '';
    const index = card.dataset.index || '0';
    const questionText = card.querySelector(".question").innerText || '';
    
    currentQuestionInfo = {career, index, questionText};
    speakQuestion(questionText, card);
}

// Speak question using TTS
function speakQuestion(questionText, card) {
    if (!('speechSynthesis' in window)) {
        startRecording(card);
        return;
    }
    
    const statusEl = card.querySelector(".record-status");
    if (statusEl) statusEl.innerText = "🔊 AI is asking question...";
    
    // Update main UI
    updateMainQuestionDisplay(questionText);
    
    const utterance = new SpeechSynthesisUtterance(questionText);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    
    utterance.onend = function() {
        if (statusEl) statusEl.innerText = "🎤 Starting recording...";
        setTimeout(() => startRecording(card), 500);
    };
    
    utterance.onerror = function() {
        if (statusEl) statusEl.innerText = "❌ TTS failed, starting recording...";
        startRecording(card);
    };
    
    speechSynthesis.cancel();
    speechSynthesis.speak(utterance);
}

// Update main question display
function updateMainQuestionDisplay(questionText) {
    const mainQuestionBox = document.getElementById('question-box');
    if (mainQuestionBox) {
        mainQuestionBox.innerHTML = `
            <div style="font-weight: 600; color: var(--primary); margin-bottom: var(--space-2);">
                Question ${parseInt(currentQuestionInfo.index) + 1}:
            </div>
            <div style="color: var(--text-primary); line-height: 1.5;">
                ${questionText}
            </div>
        `;
    }
}

// Start recording with voice detection
async function startRecording(card){
    stopAndSendRecording(false);
    
    const statusEl = card.querySelector(".record-status");
    const timerEl = card.querySelector(".timer-value");
    
    if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
        if(statusEl) statusEl.innerText = "❌ Microphone not supported";
        return;
    }
    
    try{
        GLOBAL_STREAM = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            } 
        });
        
        GLOBAL_RECORDER = new MediaRecorder(GLOBAL_STREAM);
        currentRecordingChunks = [];
        
        GLOBAL_RECORDER.ondataavailable = function(e){ 
            if(e.data && e.data.size) currentRecordingChunks.push(e.data); 
        };
        
        GLOBAL_RECORDER.onstart = function(){ 
            if(statusEl) statusEl.innerText = "🎤 Recording... Speak now!";
            startSilenceCountdown(timerEl);
            setupVoiceActivityDetection();
        };
        
        GLOBAL_RECORDER.onstop = function(){ 
            if(statusEl) statusEl.innerText = "⏹️ Stopped"; 
        };
        
        GLOBAL_RECORDER.start();
        startSilenceTimer();
        
    }catch(err){
        console.error("❌ Could not start microphone:", err);
        if(statusEl) statusEl.innerText = "❌ Microphone permission denied";
    }
}

// Voice activity detection
function setupVoiceActivityDetection() {
    if (!GLOBAL_STREAM) return;
    
    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        const microphone = audioContext.createMediaStreamSource(GLOBAL_STREAM);
        const javascriptNode = audioContext.createScriptProcessor(2048, 1, 1);
        
        analyser.smoothingTimeConstant = 0.3;
        analyser.fftSize = 1024;
        
        microphone.connect(analyser);
        analyser.connect(javascriptNode);
        javascriptNode.connect(audioContext.destination);
        
        let silenceStart = null;
        
        javascriptNode.onaudioprocess = function() {
            const array = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(array);
            
            let sum = 0;
            for (let i = 0; i < array.length; i++) {
                sum += array[i];
            }
            
            const average = sum / array.length;
            
            if (average > 20) { // Voice detected
                isUserSpeaking = true;
                lastVoiceTime = Date.now();
                silenceStart = null;
                resetSilenceTimer();
            } else {
                // Silence detected
                if (isUserSpeaking && !silenceStart) {
                    silenceStart = Date.now();
                }
                
                if (silenceStart && (Date.now() - silenceStart) > SILENCE_MS) {
                    // Continuous silence after speech
                    console.log("⏰ 10 seconds silence after speech - next question");
                    stopAndSendRecording();
                    const nextBtn = document.querySelector("#next-question-btn");
                    if (nextBtn) nextBtn.click();
                }
            }
        };
    } catch (error) {
        console.warn("❌ Voice detection failed:", error);
    }
}

// Silence timer functions
function startSilenceTimer() {
    if (silenceTimeout) clearTimeout(silenceTimeout);
    silenceTimeout = setTimeout(() => {
        console.log("⏰ Silence timeout - next question");
        stopAndSendRecording();
        const nextBtn = document.querySelector("#next-question-btn");
        if (nextBtn) nextBtn.click();
    }, SILENCE_MS);
}

function resetSilenceTimer() {
    if (silenceTimeout) {
        clearTimeout(silenceTimeout);
        startSilenceTimer();
    }
}

function startSilenceCountdown(timerEl) {
    if (!timerEl) return;
    
    let timeLeft = SILENCE_MS / 1000;
    timerEl.textContent = timeLeft;
    
    const countdown = setInterval(() => {
        timeLeft--;
        timerEl.textContent = timeLeft;
        
        if (timeLeft <= 0) {
            clearInterval(countdown);
        }
    }, 1000);
}

// Stop recording and send to server
function stopAndSendRecording(send = true){
    if(GLOBAL_RECORDER && GLOBAL_RECORDER.state !== "inactive"){
        GLOBAL_RECORDER.stop();
    }
    if(GLOBAL_STREAM){
        GLOBAL_STREAM.getTracks().forEach(t=>t.stop());
        GLOBAL_STREAM = null;
    }
    if(audioContext){
        audioContext.close();
        audioContext = null;
    }
    if(silenceTimeout) {
        clearTimeout(silenceTimeout);
        silenceTimeout = null;
    }
    
    if(send && currentRecordingChunks && currentRecordingChunks.length){
        const blob = new Blob(currentRecordingChunks, { type: 'audio/webm' });
        const reader = new FileReader();
        reader.onloadend = function(){
            const base64data = reader.result.split(',')[1];
            
            fetch('/upload_audio', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({
                    filename: `response_${Date.now()}.webm`,
                    career: currentQuestionInfo?.career || '',
                    question_index: currentQuestionInfo?.index || '',
                    question: currentQuestionInfo?.questionText || '',
                    audio_base64: base64data
                })
            })
            .then(r=>r.json())
            .then(d=>{
                console.log("✅ Upload response:", d);
                
                // Show transcript
                const visible = document.querySelector(".question-card.visible");
                if(visible && d.transcript){
                    const existingTranscript = visible.querySelector(".transcript-result");
                    if (existingTranscript) existingTranscript.remove();
                    
                    const el = document.createElement("div");
                    el.className = "transcript-result small";
                    el.style.marginTop = "8px";
                    el.style.padding = "8px";
                    el.style.background = "rgba(16, 185, 129, 0.1)";
                    el.style.borderRadius = "4px";
                    el.style.borderLeft = "3px solid var(--success)";
                    el.innerHTML = `<strong>🎯 Your Answer:</strong> ${d.transcript}`;
                    visible.appendChild(el);
                }
            })
            .catch(err=>{ 
                console.error("❌ Upload failed", err); 
            });
        };
        reader.readAsDataURL(blob);
    }
    currentRecordingChunks = [];
    currentQuestionInfo = null;
    isUserSpeaking = false;
}

// Utility functions
function escapeHtml(str){
    return String(str).replace(/[&<>"']/g, function(m){ 
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]; 
    });
}

// Export for global access
window.InterviewAI = {
    loadRole,
    startRecording,
    stopAndSendRecording,
    speakQuestion
};