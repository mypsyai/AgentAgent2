/**
 * PSYAI SuperCollider Demo Activity
 * 
 * Example usage of SCEngine with Jetpack Compose UI.
 */
package cloud.psyai.sc

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private lateinit var scEngine: SCEngine
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        scEngine = SCEngine(this)
        lifecycle.addObserver(scEngine)
        
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme()
            ) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    SCDemoScreen(scEngine, lifecycleScope)
                }
            }
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        scEngine.close()
    }
}

@Composable
fun SCDemoScreen(
    engine: SCEngine,
    scope: kotlinx.coroutines.CoroutineScope
) {
    val isRunning by engine.isRunning.collectAsState()
    val peakL by engine.peakL.collectAsState()
    val peakR by engine.peakR.collectAsState()
    
    var currentSynth by remember { mutableStateOf<Synth?>(null) }
    var frequency by remember { mutableFloatStateOf(440f) }
    var amplitude by remember { mutableFloatStateOf(0.5f) }
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Header
        Text(
            text = "PSYAI SuperCollider",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.primary
        )
        
        // Status
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(if (isRunning) Color.Green else Color.Red)
            )
            Text(
                text = if (isRunning) "Running" else "Stopped",
                style = MaterialTheme.typography.bodyMedium
            )
        }
        
        // Meter
        LevelMeter(
            leftLevel = peakL,
            rightLevel = peakR,
            modifier = Modifier
                .fillMaxWidth()
                .height(40.dp)
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Controls
        Card(
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Frequency slider
                Text("Frequency: ${frequency.toInt()} Hz")
                Slider(
                    value = frequency,
                    onValueChange = { 
                        frequency = it
                        currentSynth?.set("freq", it)
                    },
                    valueRange = 100f..2000f
                )
                
                // Amplitude slider
                Text("Amplitude: ${(amplitude * 100).toInt()}%")
                Slider(
                    value = amplitude,
                    onValueChange = { 
                        amplitude = it
                        currentSynth?.set("amp", it)
                    },
                    valueRange = 0f..1f
                )
            }
        }
        
        Spacer(modifier = Modifier.weight(1f))
        
        // Synth controls
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Button(
                onClick = {
                    if (!isRunning) {
                        engine.start()
                    }
                    currentSynth?.free()
                    currentSynth = engine.play("sine") {
                        "freq" to frequency
                        "amp" to amplitude
                        gate(true)
                    }
                },
                modifier = Modifier.weight(1f),
                enabled = true
            ) {
                Text("Play Sine")
            }
            
            Button(
                onClick = {
                    currentSynth?.set("gate", 0f)
                    currentSynth = null
                },
                modifier = Modifier.weight(1f),
                enabled = currentSynth != null
            ) {
                Text("Stop")
            }
        }
        
        // Drum buttons
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            DrumButton(
                text = "KICK",
                onClick = { engine.synth("kick") },
                modifier = Modifier.weight(1f)
            )
            DrumButton(
                text = "SNARE",
                onClick = { engine.synth("snare") },
                modifier = Modifier.weight(1f)
            )
            DrumButton(
                text = "HAT",
                onClick = { engine.synth("hihat") },
                modifier = Modifier.weight(1f)
            )
        }
        
        // Sequence button
        Button(
            onClick = {
                scope.launch {
                    engine.sequence(
                        "sine",
                        listOf(
                            60 to 200L,
                            62 to 200L,
                            64 to 200L,
                            65 to 200L,
                            67 to 400L,
                            65 to 200L,
                            64 to 200L,
                            62 to 200L,
                            60 to 400L
                        ),
                        amp = amplitude
                    )
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Play Sequence")
        }
        
        // Free all
        OutlinedButton(
            onClick = { engine.freeAll() },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Free All Synths")
        }
    }
}

@Composable
fun LevelMeter(
    leftLevel: Float,
    rightLevel: Float,
    modifier: Modifier = Modifier
) {
    Canvas(modifier = modifier) {
        val meterHeight = size.height / 2 - 4
        val meterWidth = size.width
        
        // Background
        drawRect(
            color = Color.DarkGray,
            topLeft = Offset(0f, 0f),
            size = Size(meterWidth, meterHeight)
        )
        drawRect(
            color = Color.DarkGray,
            topLeft = Offset(0f, meterHeight + 8),
            size = Size(meterWidth, meterHeight)
        )
        
        // Left level
        val leftWidth = (leftLevel.coerceIn(0f, 1f) * meterWidth)
        val leftColor = when {
            leftLevel > 0.9f -> Color.Red
            leftLevel > 0.7f -> Color.Yellow
            else -> Color.Green
        }
        drawRect(
            color = leftColor,
            topLeft = Offset(0f, 0f),
            size = Size(leftWidth, meterHeight)
        )
        
        // Right level
        val rightWidth = (rightLevel.coerceIn(0f, 1f) * meterWidth)
        val rightColor = when {
            rightLevel > 0.9f -> Color.Red
            rightLevel > 0.7f -> Color.Yellow
            else -> Color.Green
        }
        drawRect(
            color = rightColor,
            topLeft = Offset(0f, meterHeight + 8),
            size = Size(rightWidth, meterHeight)
        )
    }
}

@Composable
fun DrumButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Button(
        onClick = onClick,
        modifier = modifier.height(60.dp),
        shape = RoundedCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = MaterialTheme.colorScheme.secondary
        )
    ) {
        Text(text)
    }
}
