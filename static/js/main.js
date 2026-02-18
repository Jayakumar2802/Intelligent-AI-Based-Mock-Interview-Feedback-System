// main.js - Core interview functionality
let interviewQuestions = [];
let currentQuestionIndex = 0;
let isInterviewActive = false;
let mediaRecorder = null;
let recordedChunks = [];
let audioContext = null;
let silenceTimeout = null;

// DOM elements
function el(id) { return document.getElementById(id); }

// Initialize interview
async function initializeInterview(role) {
    console.log("🎯 Initializing interview for:", role);
    
    try {
        const response = await fetch(`/questions/${encodeURIComponent(role)}`);
        interviewQuestions = await response.json();
        
        if (interviewQuestions.length === 0) {
            throw new Error('No questions found for this role');
        }
        
        return true;
    } catch (error) {
        console.error('❌ Failed to initialize interview:', error);
        return false;
    }
}

// Start interview
async function startInterview() {
    const role = document.querySelector('.interview-layout')?.dataset.role || "{{ role }}";
    
    if (!await initializeInterview(role)) {
        alert('❌ No questions found for this role. Please try another role.');
        return;
    }
    
    isInterviewActive = true;
    currentQuestionIndex = 0;
    
    // Update UI
    el('startBtn').disabled = true;
    el('startBtn').textContent = '🎤 Interview Started';
    updateAvatarStatus('🎯 Starting interview...');
    
    // Start first question
    showQuestion(interviewQuestions[0]);
}

// Show question
async function showQuestion(questionData) {
    if (!questionData) return;
    
    const questionText = questionData.question;
    
    // Update question display
    el('question-box').innerHTML = `
        <div style="font-weight: 600; color: var(--primary); margin-bottom: var(--space-2);">
            Question ${currentQuestionIndex + 1}:
        </div>
        <div style="color: var(--text-primary); line-height: 1.5;">
            ${questionText}
        </div>
    `;
    
    // Add to chat
    addChatMessage('question', `Q${currentQuestionIndex + 1}: ${questionText}`);
    
    // Show repeat button
    el('play-tts').style.display = 'inline-flex';
    
    // Speak question
    await speakQuestion(questionText);
    
    // Start recording
    startRecording();
}

// Speak question using TTS
async function speakQuestion(text) {
    if (!('speechSynthesis' in window)) {
        return Promise.resolve();
    }
    
    return new Promise((resolve) => {
        updateAvatarStatus('🔊 Asking question...');
        el('record-state').textContent = '🔊 Question being asked...';
        el('record-state').style.color = 'var(--primary)';
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.95;
        utterance.pitch = 1.0;
        
        utterance.onend = function() {
            console.log('✅ Question spoken');
            resolve();
        };
        
        utterance.onerror = function() {
            console.log('❌ TTS error');
            resolve();
        };
        
        speechSynthesis.cancel();
        speechSynthesis.speak(utterance);
    });
}

// Start recording
async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });
        
        mediaRecorder = new MediaRecorder(stream);
        recordedChunks = [];
        
        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                recordedChunks.push(e.data);
            }
        };
        
        mediaRecorder.onstop = async () => {
            // Process recording
            await processRecording();
        };
        
        mediaRecorder.start();
        
        // Update UI
        updateAvatarStatus('🎤 Listening...');
        el('record-state').textContent = '🎤 Recording... Speak now!';
        el('record-state').style.color = 'var(--success)';
        
        // Start silence timer
        startSilenceTimer();
        
    } catch (error) {
        console.error('❌ Recording failed:', error);
        el('record-state').textContent = '❌ Microphone access denied';
        el('record-state').style.color = 'var(--error)';
    }
}

// Process recording
async function processRecording() {
    if (recordedChunks.length === 0) return;
    
    const blob = new Blob(recordedChunks, { type: 'audio/webm' });
    const base64 = await blobToBase64(blob);
    
    try {
        // Send to server for transcription
        const response = await fetch('/upload_audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                audio_base64: base64.split(',')[1],
                question: interviewQuestions[currentQuestionIndex].question
            })
        });
        
        const result = await response.json();
        
        if (result.transcript) {
            // Show transcript
            el('transcript').innerHTML = `
                <div style="padding: var(--space-4);">
                    <div style="font-weight: 600; color: var(--primary); margin-bottom: var(--space-2);">
                        🎯 Your Answer:
                    </div>
                    <div style="color: var(--text-primary); line-height: 1.5; background: white; padding: var(--space-4); border-radius: var(--radius); border-left: 4px solid var(--primary);">
                        ${result.transcript}
                    </div>
                </div>
            `;
        }
        
        // Get AI suggested answer
        await getSuggestedAnswer();
        
        // Move to next question after delay
        setTimeout(() => {
            nextQuestion();
        }, 3000);
        
    } catch (error) {
        console.error('❌ Processing failed:', error);
    }
}

// Get suggested answer from AI
async function getSuggestedAnswer() {
    try {
        const response = await fetch('/generate_answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: interviewQuestions[currentQuestionIndex].question,
                role: "{{ role }}"
            })
        });
        
        const result = await response.json();
        
        if (result.answer) {
            addChatMessage('answer', result.answer);
        }
    } catch (error) {
        console.error('❌ Failed to get suggested answer:', error);
    }
}

// Next question
function nextQuestion() {
    if (!isInterviewActive) return;
    
    currentQuestionIndex++;
    
    if (currentQuestionIndex < interviewQuestions.length) {
        showQuestion(interviewQuestions[currentQuestionIndex]);
        updateProgress();
    } else {
        endInterview();
    }
}

// End interview
function endInterview() {
    isInterviewActive = false;
    
    el('question-box').innerHTML = `
        <div style="text-align: center; color: var(--success); padding: var(--space-8);">
            <div style="font-size: 48px; margin-bottom: var(--space-3);">🎉</div>
            <div style="font-size: var(--font-size-lg); font-weight: 600;">Interview Completed!</div>
            <div style="color: var(--text-muted); margin-top: var(--space-2);">Great job! You've completed all questions.</div>
        </div>
    `;
    
    el('record-state').textContent = '✅ Interview completed';
    el('record-state').style.color = 'var(--success)';
    updateAvatarStatus('✅ Interview completed');
    
    updateProgress(true);
}

// Update progress
function updateProgress(completed = false) {
    const summary = el('summary');
    if (!summary) return;
    
    if (completed) {
        summary.innerHTML = `
            <div style="display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3);">
                <div style="width: 12px; height: 12px; background: var(--success); border-radius: 50%;"></div>
                <div>Interview completed</div>
            </div>
            <div style="display: flex; align-items: center; gap: var(--space-3);">
                <div style="width: 12px; height: 12px; background: var(--success); border-radius: 50%;"></div>
                <div>All ${interviewQuestions.length} questions answered</div>
            </div>
        `;
    } else {
        summary.innerHTML = `
            <div style="display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3);">
                <div style="width: 12px; height: 12px; background: var(--success); border-radius: 50%;"></div>
                <div>Interview in progress</div>
            </div>
            <div style="display: flex; align-items: center; gap: var(--space-3);">
                <div style="width: 12px; height: 12px; background: var(--primary); border-radius: 50%;"></div>
                <div>Question ${currentQuestionIndex + 1} of ${interviewQuestions.length}</div>
            </div>
        `;
    }
}

// Add chat message
function addChatMessage(type, text) {
    const chatBody = el('chatBody');
    if (!chatBody) return;
    
    // Clear initial message
    if (chatBody.querySelector('.initial-message')) {
        chatBody.innerHTML = '';
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;
    
    if (type === 'question') {
        messageDiv.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: var(--space-3);">
                <div style="width: 24px; height: 24px; background: var(--primary); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: 600; flex-shrink: 0;">Q</div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; color: var(--primary); margin-bottom: var(--space-2);">AI Interviewer</div>
                    <div style="color: var(--text-primary); line-height: 1.5;">${text}</div>
                </div>
            </div>
        `;
    } else if (type === 'answer') {
        messageDiv.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: var(--space-3);">
                <div style="width: 24px; height: 24px; background: var(--success); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: 600; flex-shrink: 0;">A</div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; color: var(--success); margin-bottom: var(--space-2);">Suggested Answer</div>
                    <div style="color: var(--text-primary); line-height: 1.5;">${text}</div>
                    <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: var(--space-2);">
                        💡 AI-generated reference answer
                    </div>
                </div>
            </div>
        `;
    }
    
    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

// Utility functions
function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

function updateAvatarStatus(status) {
    const statusElement = el('avatarStatus');
    if (statusElement) {
        statusElement.textContent = status;
    }
}

function startSilenceTimer() {
    if (silenceTimeout) clearTimeout(silenceTimeout);
    silenceTimeout = setTimeout(() => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        }
    }, 10000);
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Start interview button
    if (el('startBtn')) {
        el('startBtn').addEventListener('click', startInterview);
    }
    
    // Stop button
    if (el('stopBtn')) {
        el('stopBtn').addEventListener('click', function() {
            if (isInterviewActive && confirm('Stop the interview?')) {
                endInterview();
            }
        });
    }
    
    // Next question button
    if (el('nextQ')) {
        el('nextQ').addEventListener('click', function() {
            if (isInterviewActive && confirm('Move to next question?')) {
                if (mediaRecorder && mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                } else {
                    nextQuestion();
                }
            }
        });
    }
    
    // Repeat question button
    if (el('play-tts')) {
        el('play-tts').addEventListener('click', function() {
            if (isInterviewActive && interviewQuestions[currentQuestionIndex]) {
                speakQuestion(interviewQuestions[currentQuestionIndex].question);
            }
        });
    }
    
    // Initialize webcam
    initializeWebcam();
});

// Webcam initialization
async function initializeWebcam() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        if (el('studentCam')) {
            el('studentCam').srcObject = stream;
        }
    } catch (error) {
        console.warn('📹 Camera not available:', error);
        const fallback = document.querySelector('.camera-fallback');
        if (fallback) fallback.style.display = 'flex';
    }
}