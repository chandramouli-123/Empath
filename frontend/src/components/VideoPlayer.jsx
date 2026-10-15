import { useRef, useEffect, useCallback } from 'react'
import YouTube from 'react-youtube'

function extractVideoId(url) {
  try {
    const u = new URL(url)
    return u.searchParams.get('v') || u.pathname.split('/').pop() || ''
  } catch {
    return url // assume it's already an ID
  }
}

export default function VideoPlayer({
  url, onPause, onPlay, onSeek, onTimeUpdate, pauseForMissingFace, resumeToken
}) {
  const videoId = extractVideoId(url)
  const lastTimeRef = useRef(0)
  const playerRef = useRef(null)
  const timeIntervalRef = useRef(null)
  const onTimeUpdateRef = useRef(onTimeUpdate)

  useEffect(() => {
    onTimeUpdateRef.current = onTimeUpdate
  }, [onTimeUpdate])

  // Poll current video time every second so the UI can show real YouTube timestamps
  useEffect(() => {
    timeIntervalRef.current = setInterval(() => {
      if (playerRef.current && typeof playerRef.current.getCurrentTime === 'function') {
        try {
          const t = playerRef.current.getCurrentTime()
          if (t != null) {
            lastTimeRef.current = t
            onTimeUpdateRef.current?.(t)
          }
        } catch { /* player not ready */ }
      }
    }, 1000)
    return () => clearInterval(timeIntervalRef.current)
  }, [])

  useEffect(() => {
    if (pauseForMissingFace && playerRef.current) {
      playerRef.current.pauseVideo()
    }
  }, [pauseForMissingFace])

  useEffect(() => {
    if (resumeToken && playerRef.current) {
      playerRef.current.playVideo()
    }
  }, [resumeToken])

  const opts = {
    width: '100%',
    height: '100%',
    playerVars: {
      autoplay: 1,
      modestbranding: 1,
      rel: 0,
    },
  }

  function onReady(e) {
    playerRef.current = e.target
  }

  function onStateChange(e) {
    const player = e.target
    const state = e.data

    // YouTube player states: -1=unstarted, 0=ended, 1=playing, 2=paused, 3=buffering, 5=cued
    if (state === 2) onPause?.(player.getCurrentTime())
    if (state === 1) {
      const current = player.getCurrentTime()
      if (Math.abs(current - lastTimeRef.current) > 3) {
        // Jumped more than 3s — treat as seek (rewind or fast-forward)
        if (current < lastTimeRef.current) onSeek?.('rewind', current)
        else onSeek?.('fast_forward', current)
      }
      onPlay?.(current)
      lastTimeRef.current = current
    }
  }

  if (!videoId) {
    return (
      <div className="w-full aspect-video bg-surface rounded-2xl flex items-center justify-center text-gray-600">
        Invalid YouTube URL
      </div>
    )
  }

  return (
    <div className="w-full aspect-video rounded-2xl overflow-hidden">
      <YouTube
        videoId={videoId}
        opts={opts}
        onReady={onReady}
        onStateChange={onStateChange}
        className="w-full h-full"
        iframeClassName="w-full h-full"
      />
    </div>
  )
}
