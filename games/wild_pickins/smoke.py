"""Small E02 scaffold check; does not validate Wild Pickins mechanics or RTP."""
from pathlib import Path
from game_config import GameConfig
from gamestate import GameState

if __name__ == "__main__":
    config = GameConfig()
    assert config.game_id == "wild_pickins"
    assert Path(config.reels_path).resolve() == Path(__file__).resolve().parent / "reels"
    state = GameState(config)
    state.betmode = "base"
    state.criteria = "basegame"
    state.run_spin(0)
    print("PASS: isolated template configuration, reels and seed-0 base round")
