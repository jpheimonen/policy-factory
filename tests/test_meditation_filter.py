"""Tests for the MeditationFilter."""

from policy_factory.agent.meditation_filter import MeditationFilter


class TestMeditationFilterDetection:
    """Tests for meditation pattern detection."""

    def test_initial_state_is_detecting(self) -> None:
        filt = MeditationFilter()
        assert filt.state == "detecting"

    def test_detects_meditation_start_with_countdown(self) -> None:
        filt = MeditationFilter()
        result = filt.process("10. Ideological leanings — I notice that")
        assert result is False
        assert filt.state == "meditating"

    def test_detects_meditation_start_with_colon(self) -> None:
        filt = MeditationFilter()
        result = filt.process("10: Ideological leanings")
        assert result is False
        assert filt.state == "meditating"

    def test_detects_meditation_start_after_newline(self) -> None:
        filt = MeditationFilter()
        result = filt.process("Let me begin.\n10. Ideological leanings")
        assert result is False
        assert filt.state == "meditating"

    def test_no_meditation_detected_after_threshold(self) -> None:
        filt = MeditationFilter()
        # Send enough text without a "10" pattern
        chunk = "This is regular analysis content. " * 20
        result = filt.process(chunk)
        assert filt.state == "streaming"
        assert result is True

    def test_no_meditation_streams_everything(self) -> None:
        filt = MeditationFilter()
        # Large chunk without meditation pattern
        chunk = "A" * 600
        result = filt.process(chunk)
        assert result is True
        assert filt.state == "streaming"

    def test_subsequent_chunks_stream_after_detection_threshold(self) -> None:
        filt = MeditationFilter()
        filt.process("A" * 600)
        assert filt.state == "streaming"
        # Subsequent chunks should stream
        assert filt.process("more content") is True


class TestMeditationFilterSuppression:
    """Tests for meditation content suppression."""

    def test_suppresses_meditation_content(self) -> None:
        filt = MeditationFilter()
        # Start meditation
        assert filt.process("10. Ideological leanings") is False
        # Middle of countdown
        assert filt.process("\n9. Cultural assumptions") is False
        assert filt.process("\n8. Recency bias") is False

    def test_meditation_chunks_are_not_streamed(self) -> None:
        filt = MeditationFilter()
        results = []
        chunks = [
            "10. Ideological leanings\n",
            "9. Cultural assumptions\n",
            "8. Recency bias\n",
            "7. Confirmation bias\n",
            "6. Anchoring effects\n",
            "5. Western-centric framing\n",
            "4. Techno-optimism\n",
            "3. Status quo bias\n",
            "2. Elite perspective bias\n",
        ]
        for chunk in chunks:
            results.append(filt.process(chunk))

        # All meditation chunks should be suppressed
        assert all(r is False for r in results)


class TestMeditationFilterTransition:
    """Tests for detecting the end of meditation and transitioning to streaming."""

    def test_detects_end_of_meditation_at_one(self) -> None:
        filt = MeditationFilter()
        # Start meditation
        filt.process("10. Ideological leanings\n")
        assert filt.state == "meditating"

        # Process through countdown
        for i in range(9, 1, -1):
            filt.process(f"\n{i}. Some reflection\n")

        # Hit "1" — the end marker
        result = filt.process("\n1. Other biases\nNow here is the actual analysis.\n")
        assert result is False  # The chunk containing "1" is still meditation

    def test_full_countdown_then_analysis(self) -> None:
        filt = MeditationFilter()

        # Full meditation countdown
        meditation_text = "10. Ideological leanings\n"
        for i in range(9, 1, -1):
            meditation_text += f"{i}. Some reflection\n"
        meditation_text += "1. Other biases I notice\n"

        # Process meditation as one chunk — should be suppressed
        result = filt.process(meditation_text)
        assert result is False

        # The transition chunk — the filter detects the end of meditation
        # ("1." was in the first chunk, but END_PATTERN search runs on
        # the second call). This chunk triggers the state transition
        # but is itself still suppressed (it completes the meditation).
        result = filt.process("\nNow let me proceed to the analysis.\n")
        assert filt.state == "streaming"
        # The transition chunk is suppressed — the next chunk streams
        assert result is False

        # Subsequent chunks stream freely
        result = filt.process("The actual analysis begins.")
        assert result is True

    def test_post_meditation_content_streams(self) -> None:
        filt = MeditationFilter()
        # Start and complete meditation
        meditation = "10. Bias one\n9. Bias two\n8. Three\n7. Four\n6. Five\n"
        meditation += "5. Six\n4. Seven\n3. Eight\n2. Nine\n1. Ten\n"
        filt.process(meditation)

        # Post-meditation
        filt.process("\nAnalysis begins here.\n")
        assert filt.state == "streaming"

        # Further chunks stream freely
        assert filt.process("More analysis") is True
        assert filt.process("Even more") is True


class TestMeditationFilterReset:
    """Tests for the reset method."""

    def test_reset_returns_to_detecting(self) -> None:
        filt = MeditationFilter()
        filt.process("10. Something")
        assert filt.state == "meditating"

        filt.reset()
        assert filt.state == "detecting"

    def test_reset_clears_buffer(self) -> None:
        filt = MeditationFilter()
        filt.process("some text")
        filt.reset()
        # After reset, should start fresh
        assert filt._buffer == ""


class TestMeditationFilterEdgeCases:
    """Edge cases and conservative behaviour."""

    def test_empty_chunk_does_not_crash(self) -> None:
        filt = MeditationFilter()
        result = filt.process("")
        assert isinstance(result, bool)

    def test_number_10_in_middle_of_text_does_not_trigger(self) -> None:
        filt = MeditationFilter()
        # "10" appearing mid-sentence should not trigger meditation
        filt.process("There are 10 items in the list and here is more context. " * 15)
        # If buffer exceeds threshold, should start streaming
        assert filt.state == "streaming"

    def test_streaming_state_is_permanent(self) -> None:
        filt = MeditationFilter()
        filt.process("A" * 600)
        assert filt.state == "streaming"

        # Even if we see "10." now, we stay streaming
        result = filt.process("10. This is not meditation")
        assert result is True
        assert filt.state == "streaming"

    def test_small_chunks_accumulate(self) -> None:
        filt = MeditationFilter()
        # Small chunks that don't exceed threshold
        for _ in range(10):
            filt.process("hello ")
        # Should still be detecting (under threshold)
        assert filt.state == "detecting"
