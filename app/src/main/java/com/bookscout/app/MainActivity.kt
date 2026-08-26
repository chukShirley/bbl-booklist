package com.bookscout.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.QrCodeScanner
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    private lateinit var database: BookDatabase

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        database = BookDatabase(applicationContext)
        setContent { BookScoutApp(database) }
    }
}

private val Night = Color(0xFF29262B)
private val Charcoal = Color(0xFF3C3541)
private val Purple = Color(0xFFAC5FDB)
private val Lavender = Color(0xFFE3A2EE)
private val SoftWhite = Color(0xFFF8F2FA)

@Composable
fun BookScoutApp(database: BookDatabase) {
    val context = LocalContext.current
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf(database.recentBooks()) }
    var searched by remember { mutableStateOf(false) }

    val scanner = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        result.data?.getStringExtra(ScannerActivity.RESULT_ISBN)?.let {
            query = it
            results = database.search(it)
            searched = true
        }
    }
    val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) scanner.launch(Intent(context, ScannerActivity::class.java))
    }
    fun scan() {
        if (context.checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            scanner.launch(Intent(context, ScannerActivity::class.java))
        } else cameraPermission.launch(Manifest.permission.CAMERA)
    }
    fun search() {
        results = database.search(query)
        searched = query.isNotBlank()
    }

    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Purple,
            onPrimary = Color.White,
            secondary = Lavender,
            onSecondary = Night,
            background = Night,
            onBackground = SoftWhite,
            surface = Charcoal,
            onSurface = SoftWhite,
            surfaceVariant = Color(0xFF4A4250),
            onSurfaceVariant = Color(0xFFE2D8E5),
        ),
    ) {
        Scaffold(containerColor = Night) { padding ->
            Column(
                Modifier.fillMaxSize().padding(padding).padding(horizontal = 20.dp),
            ) {
                Spacer(Modifier.height(24.dp))
                Text("BOOK SCOUT", style = MaterialTheme.typography.labelLarge, color = Lavender)
                Text("Is this one on the list?", style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold, color = SoftWhite)
                Spacer(Modifier.height(18.dp))
                Button(
                    onClick = ::scan, modifier = Modifier.fillMaxWidth().height(64.dp),
                    shape = RoundedCornerShape(18.dp),
                ) {
                    Icon(Icons.Rounded.QrCodeScanner, null)
                    Spacer(Modifier.width(10.dp))
                    Text("Scan ISBN barcode", style = MaterialTheme.typography.titleMedium)
                }
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = query, onValueChange = { query = it }, modifier = Modifier.fillMaxWidth(),
                    label = { Text("Title, author, ISBN, or list") }, singleLine = true,
                    leadingIcon = { Icon(Icons.Rounded.Search, null) },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { search() }),
                    trailingIcon = { TextButton(onClick = { search() }) { Text("CHECK") } },
                    shape = RoundedCornerShape(16.dp),
                )
                Spacer(Modifier.height(18.dp))
                when {
                    results.isEmpty() && searched -> NotFound(query)
                    else -> {
                        Text(
                            if (searched) "${results.size} ${if (results.size == 1) "match" else "matches"}" else "Books to look for",
                            style = MaterialTheme.typography.titleMedium, color = SoftWhite,
                        )
                        Spacer(Modifier.height(8.dp))
                        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 28.dp)) {
                            items(results, key = { it.id }) { book ->
                                BookCard(book) { owned ->
                                    database.setOwned(book.id, owned)
                                    results = database.search(query)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun NotFound(query: String) {
    Card(colors = CardDefaults.cardColors(containerColor = Lavender, contentColor = Night)) {
        Column(Modifier.fillMaxWidth().padding(20.dp)) {
            Text("Not found", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text("“$query” isn’t on the downloaded lists. Check the spelling or try the author.")
        }
    }
}

@Composable
private fun BookCard(book: BookMatch, onOwnedChanged: (Boolean) -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Charcoal), shape = RoundedCornerShape(18.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Row(verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f)) {
                    Text(book.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = SoftWhite)
                    Text(book.author, style = MaterialTheme.typography.bodyLarge, color = Color(0xFFD0C5D3))
                }
                AssistChip(
                    onClick = {},
                    label = { Text(if (book.owned) "OWNED" else book.priority.uppercase()) },
                    colors = AssistChipDefaults.assistChipColors(
                        containerColor = if (book.owned) Lavender else Purple,
                        labelColor = if (book.owned) Night else Color.White,
                    ),
                )
            }
            Spacer(Modifier.height(10.dp))
            book.lists.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium, color = Lavender) }
            if (book.notes.isNotBlank()) {
                Spacer(Modifier.height(6.dp)); Text(book.notes, style = MaterialTheme.typography.bodySmall)
            }
            if (book.isbn13 != null) Text("ISBN ${book.isbn13}", style = MaterialTheme.typography.labelSmall, color = Color(0xFFB8AEBB))
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = { onOwnedChanged(!book.owned) }) {
                Text(if (book.owned) "Mark as not owned" else "We bought this")
            }
        }
    }
}
