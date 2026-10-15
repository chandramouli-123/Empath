import { useRef, useState, useCallback, useEffect } from 'react'

export function useWebcam() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const [hasPermission, setHasPermission] = useState(null) // null=unknown, true, false
  const [stream, setStream] = useState(null)

  const attachStreamToVideo = useCallback((mediaStream) => {
    if (videoRef.current && mediaStream) {
      if (videoRef.current.srcObject !== mediaStream) {
        videoRef.current.srcObject = mediaStream
      }
      videoRef.current.play().catch(() => {
        // Browser autoplay policy might require user gesture or muted
      })
    }
  }, [])

  const requestPermission = useCallback(async () => {
    // If stream is already active and live, reuse it
    if (streamRef.current && streamRef.current.getVideoTracks().some(t => t.readyState === 'live')) {
      setHasPermission(true)
      attachStreamToVideo(streamRef.current)
      return
    }

    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false
      })
      streamRef.current = s
      setStream(s)
      setHasPermission(true)
      attachStreamToVideo(s)
    } catch (err) {
      console.error('getUserMedia permission error:', err)
      setHasPermission(false)
    }
  }, [attachStreamToVideo])

  // Sync stream to video element when either changes
  useEffect(() => {
    if (streamRef.current && videoRef.current) {
      attachStreamToVideo(streamRef.current)
    }
  }, [hasPermission, stream, attachStreamToVideo])

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
      setStream(null)
    }
  }, [])

  // Returns a Promise<Blob|null> — captured JPEG frame
  const captureFrame = useCallback(() => {
    return new Promise((resolve) => {
      const video = videoRef.current
      const canvas = canvasRef.current
      const currentStream = streamRef.current

      if (!video || !canvas || !currentStream) return resolve(null)
      // Ensure video is actively playing and has dimensions
      if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
        return resolve(null)
      }

      try {
        const ctx = canvas.getContext('2d')
        const vw = video.videoWidth
        const vh = video.videoHeight

        // Capture full field of view (320x240) so hands and phones held to the side are not cropped out
        canvas.width = 320
        canvas.height = 240
        ctx.drawImage(video, 0, 0, vw, vh, 0, 0, 320, 240)
        canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.8)
      } catch (err) {
        console.error('captureFrame error:', err)
        resolve(null)
      }
    })
  }, [])

  // Cleanup tracks ONLY when component truly unmounts
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop())
        streamRef.current = null
      }
    }
  }, [])

  return { videoRef, canvasRef, hasPermission, stream, requestPermission, captureFrame, stopStream }
}
