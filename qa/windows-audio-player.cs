// Public fixture player: GUI subsystem avoids stealing the dictation target.
using System.Media;
internal static class SaywardAudioFixture {
    [System.STAThread]
    private static void Main(string[] args) {
        using (var player = new SoundPlayer(args[0])) { player.PlaySync(); }
    }
}
