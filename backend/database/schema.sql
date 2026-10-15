-- =============================================================================
-- Empath Database Schema for Supabase
-- Run this in the Supabase SQL Editor (Dashboard -> SQL Editor -> New query)
-- =============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Sessions Table
CREATE TABLE IF NOT EXISTS public.sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id TEXT NOT NULL DEFAULT 'student_001',
    video_id TEXT,
    topic TEXT DEFAULT 'General',
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL,
    ended_at TIMESTAMPTZ
);

-- 2. Emotion Events Table
CREATE TABLE IF NOT EXISTS public.emotion_events (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES public.sessions(id) ON DELETE CASCADE,
    timestamp_seconds DOUBLE PRECISION NOT NULL,
    emotion TEXT NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 0.0,
    focus_score NUMERIC DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Behavior Events Table
CREATE TABLE IF NOT EXISTS public.behavior_events (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES public.sessions(id) ON DELETE CASCADE,
    timestamp_seconds DOUBLE PRECISION NOT NULL,
    event_type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. Suggestions Table
CREATE TABLE IF NOT EXISTS public.suggestions (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES public.sessions(id) ON DELETE CASCADE,
    timestamp_seconds DOUBLE PRECISION NOT NULL,
    engagement_state TEXT,
    suggestion_text TEXT,
    action TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. Session Logs (Detailed Real-time Metrics)
CREATE TABLE IF NOT EXISTS public.session_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp_seconds DOUBLE PRECISION NOT NULL,
    emotion TEXT,
    seqi_score INTEGER DEFAULT 0,
    be DOUBLE PRECISION DEFAULT 0.0,
    es DOUBLE PRECISION DEFAULT 0.0,
    id_score DOUBLE PRECISION DEFAULT 0.0,
    rr DOUBLE PRECISION DEFAULT 0.0,
    engagement_state TEXT,
    trend_slope DOUBLE PRECISION DEFAULT 0.0,
    behavior_events JSONB DEFAULT '[]'::jsonb,
    is_distracted BOOLEAN DEFAULT FALSE,
    distraction_reasons JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 6. Session Feedback (Cross-Session Adaptability)
CREATE TABLE IF NOT EXISTS public.session_feedback (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    student_id TEXT NOT NULL,
    final_seqi DOUBLE PRECISION DEFAULT 0.0,
    emotion_pattern JSONB DEFAULT '{}'::jsonb,
    drift_segments JSONB DEFAULT '[]'::jsonb,
    quiz_score DOUBLE PRECISION,
    recovery_metrics JSONB DEFAULT '[]'::jsonb,
    key_segments JSONB DEFAULT '{}'::jsonb,
    risk_level TEXT DEFAULT 'green',
    total_time DOUBLE PRECISION DEFAULT 0.0,
    active_time DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 7. Quiz Results Table
CREATE TABLE IF NOT EXISTS public.quiz_results (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    questions JSONB NOT NULL,
    answers JSONB DEFAULT '[]'::jsonb,
    scores JSONB DEFAULT '[]'::jsonb,
    total_score DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- =============================================================================
-- Performance Indexes
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_emotion_events_session ON public.emotion_events(session_id, timestamp_seconds);
CREATE INDEX IF NOT EXISTS idx_behavior_events_session ON public.behavior_events(session_id, timestamp_seconds);
CREATE INDEX IF NOT EXISTS idx_suggestions_session ON public.suggestions(session_id, timestamp_seconds);
CREATE INDEX IF NOT EXISTS idx_session_logs_session ON public.session_logs(session_id, timestamp_seconds);
CREATE INDEX IF NOT EXISTS idx_session_feedback_student ON public.session_feedback(student_id);
CREATE INDEX IF NOT EXISTS idx_quiz_results_session ON public.quiz_results(session_id);

-- =============================================================================
-- Row Level Security (RLS) & Access Policies
-- Enable RLS and grant full read/write access to anon & authenticated clients
-- =============================================================================
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emotion_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.behavior_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.session_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.session_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_results ENABLE ROW LEVEL SECURITY;

-- Allow anon and authenticated roles full access
DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN (
        'sessions', 'emotion_events', 'behavior_events', 'suggestions', 
        'session_logs', 'session_feedback', 'quiz_results'
    )
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS "Allow all for anon" ON public.%I', tbl);
        EXECUTE format('CREATE POLICY "Allow all for anon" ON public.%I FOR ALL TO anon USING (true) WITH CHECK (true)', tbl);

        EXECUTE format('DROP POLICY IF EXISTS "Allow all for authenticated" ON public.%I', tbl);
        EXECUTE format('CREATE POLICY "Allow all for authenticated" ON public.%I FOR ALL TO authenticated USING (true) WITH CHECK (true)', tbl);
    END LOOP;
END $$;
