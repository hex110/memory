class InteractionTools:
    def __init__(self, tts_engine):
        self.tts_engine = tts_engine
        
    async def text_to_speech(self, message: str):
        """Play message through text to speech."""
        await self.tts_engine.play_text(message)
        return {"status": "success", "message": "Audio played successfully"}