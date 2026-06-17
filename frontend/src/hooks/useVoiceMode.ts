import { useState, useEffect, useCallback, useRef } from 'react';

export type VoiceStatus = 'idle' | 'listening' | 'thinking' | 'speaking';

export function useVoiceMode(onUserSpoke: (text: string) => void) {
    const [isVoiceMode, setIsVoiceMode] = useState(false);
    const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>('idle');
    const [transcript, setTranscript] = useState('');
    const [llmReply, setLlmReply] = useState('');
    
    const recognitionRef = useRef<any>(null);
    const synthRef = useRef<SpeechSynthesis | null>(null);

    // Keep track of the latest voiceStatus for the onend callback closure
    const statusRef = useRef(voiceStatus);
    useEffect(() => { statusRef.current = voiceStatus; }, [voiceStatus]);

    const onUserSpokeRef = useRef(onUserSpoke);
    useEffect(() => { onUserSpokeRef.current = onUserSpoke; }, [onUserSpoke]);

    useEffect(() => {
        if (typeof window !== 'undefined') {
            synthRef.current = window.speechSynthesis;
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            if (SpeechRecognition) {
                const recognition = new SpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = true;
                recognition.lang = 'en-US';

                recognition.onresult = (event: any) => {
                    let finalTranscript = '';
                    let interimTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; ++i) {
                        if (event.results[i].isFinal) {
                            finalTranscript += event.results[i][0].transcript;
                        } else {
                            interimTranscript += event.results[i][0].transcript;
                        }
                    }
                    if (interimTranscript) {
                        setTranscript(interimTranscript);
                    }
                    if (finalTranscript) {
                        setTranscript(finalTranscript);
                        setVoiceStatus('thinking');
                        onUserSpokeRef.current(finalTranscript);
                    }
                };

                recognition.onerror = (event: any) => {
                    if (event.error !== 'no-speech') {
                        console.error("Speech recognition error", event.error);
                    }
                    if (event.error === 'no-speech' || event.error === 'network') {
                        setVoiceStatus('idle');
                    }
                };

                recognition.onend = () => {
                    if (statusRef.current === 'listening') {
                        setVoiceStatus('idle');
                    }
                };

                recognitionRef.current = recognition;
            }
        }
        
        return () => {
            if (recognitionRef.current) recognitionRef.current.stop();
            if (synthRef.current) synthRef.current.cancel();
        }
    }, []);

    const startListening = useCallback(() => {
        if (recognitionRef.current && isVoiceMode) {
            setTranscript('');
            setLlmReply('');
            setVoiceStatus('listening');
            try {
                recognitionRef.current.start();
            } catch (e) {
                // Already started
            }
        }
    }, [isVoiceMode]);

    const stopListening = useCallback(() => {
        if (recognitionRef.current) {
            recognitionRef.current.stop();
        }
        setVoiceStatus('idle');
    }, []);

    const speakText = useCallback((text: string) => {
        if (!synthRef.current) return;
        setVoiceStatus('speaking');
        setLlmReply(text);
        
        const cleanText = text.replace(/<[^>]*>?/gm, '').replace(/[*_#]/g, '');
        
        const utterance = new SpeechSynthesisUtterance(cleanText);
        const voices = synthRef.current.getVoices();
        const googleVoice = voices.find(v => v.name.includes("Google US English") || v.name.includes("Natural"));
        if (googleVoice) utterance.voice = googleVoice;
        
        utterance.onend = () => {
            if (isVoiceMode) {
                startListening();
            } else {
                setVoiceStatus('idle');
            }
        };
        
        synthRef.current.cancel();
        synthRef.current.speak(utterance);
    }, [isVoiceMode, startListening]);
    
    // Toggle side effects
    useEffect(() => {
        if (isVoiceMode) {
            startListening();
        } else {
            if (synthRef.current) synthRef.current.cancel();
            if (recognitionRef.current) recognitionRef.current.stop();
            setVoiceStatus('idle');
        }
    }, [isVoiceMode, startListening]);

    const interrupt = useCallback(() => {
        if (synthRef.current) synthRef.current.cancel();
        setTimeout(() => {
            if (isVoiceMode) startListening();
        }, 100);
    }, [isVoiceMode, startListening]);

    return {
        isVoiceMode,
        setIsVoiceMode,
        voiceStatus,
        transcript,
        llmReply,
        startListening,
        stopListening,
        speakText,
        setVoiceStatus,
        interrupt
    };
}
