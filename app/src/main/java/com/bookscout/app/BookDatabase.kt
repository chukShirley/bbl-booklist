package com.bookscout.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import java.text.Normalizer

data class BookMatch(
    val id: Long,
    val title: String,
    val author: String,
    val isbn13: String?,
    val lists: List<String>,
    val priority: String = "medium",
    val notes: String = "",
    val owned: Boolean,
    val exact: Boolean = false,
)

class BookDatabase(private val context: Context) {
    private val database: SQLiteDatabase by lazy {
        val file = context.getDatabasePath("book-scout.db")
        if (!file.exists()) {
            file.parentFile?.mkdirs()
            context.assets.open("book-scout.db").use { input ->
                file.outputStream().use { output -> input.copyTo(output) }
            }
        }
        SQLiteDatabase.openDatabase(file.path, null, SQLiteDatabase.OPEN_READWRITE).also {
            it.execSQL("PRAGMA foreign_keys=ON")
        }
    }

    fun search(rawQuery: String): List<BookMatch> {
        val query = rawQuery.trim()
        if (query.isBlank()) return recentBooks()
        val isbn = normalizeIsbn(query)
        if (isbn.length == 10 || isbn.length == 13) {
            books("EXISTS (SELECT 1 FROM book_identifiers bi WHERE bi.book_id=b.id AND bi.value=?)", arrayOf(isbn), true)
                .let { if (it.isNotEmpty()) return it }
        }
        val normalized = normalizeText(query)
        val terms = normalized.split(" ").filter { it.isNotBlank() }.distinct()
        val termClause = terms.joinToString(" AND ") {
            "(b.normalized_title LIKE ? OR b.normalized_author LIKE ? OR EXISTS " +
                "(SELECT 1 FROM book_lists bx JOIN lists lx ON lx.id=bx.list_id " +
                "WHERE bx.book_id=b.id AND lx.name LIKE ?))"
        }
        val termArgs = terms.flatMap { term -> listOf("%$term%", "%$term%", "%$term%") }.toTypedArray()
        val candidates = books(termClause, termArgs)
        if (candidates.isNotEmpty()) return candidates
        return books("1=1", emptyArray()).map { book ->
            book to maxOf(
                similarity(normalized, normalizeText(book.title)),
                similarity(normalized, normalizeText("${book.title} ${book.author}")),
            )
        }.filter { it.second >= 0.52 }.sortedByDescending { it.second }.take(10).map { it.first }
    }

    fun recentBooks(): List<BookMatch> = books("1=1", emptyArray()).take(30)

    private fun books(where: String, args: Array<String>, exact: Boolean = false): List<BookMatch> {
        val sql = """
            SELECT b.id,b.title,b.author,
              (SELECT value FROM book_identifiers WHERE book_id=b.id AND scheme='ISBN13' LIMIT 1),
              GROUP_CONCAT(DISTINCT l.name),COALESCE(i.notes,''),CASE WHEN i.book_id IS NULL THEN 0 ELSE 1 END
            FROM books b LEFT JOIN book_lists bl ON bl.book_id=b.id LEFT JOIN lists l ON l.id=bl.list_id
            LEFT JOIN inventory i ON i.book_id=b.id WHERE $where
            GROUP BY b.id ORDER BY (i.book_id IS NULL) DESC,b.title COLLATE NOCASE LIMIT 250
        """.trimIndent()
        return database.rawQuery(sql, args).use { cursor ->
            buildList {
                while (cursor.moveToNext()) add(
                    BookMatch(
                        cursor.getLong(0), cursor.getString(1), cursor.getString(2), cursor.getString(3),
                        cursor.getString(4)?.split(",") ?: emptyList(), notes = cursor.getString(5),
                        owned = cursor.getInt(6) == 1, exact = exact,
                    )
                )
            }
        }
    }

    fun setOwned(id: Long, owned: Boolean) {
        if (owned) {
            database.insertWithOnConflict(
                "inventory", null, ContentValues().apply { put("book_id", id); put("quantity", 1) },
                SQLiteDatabase.CONFLICT_IGNORE,
            )
        } else database.delete("inventory", "book_id=?", arrayOf(id.toString()))
    }

    companion object {
        fun normalizeText(value: String): String = Normalizer.normalize(value, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "").lowercase().replace(Regex("[^a-z0-9]+"), " ").trim()
        fun normalizeIsbn(value: String): String = value.uppercase().filter { it.isDigit() || it == 'X' }

        private fun similarity(a: String, b: String): Double {
            if (a.isBlank() || b.isBlank()) return 0.0
            var previous = IntArray(b.length + 1) { it }
            for (i in a.indices) {
                val current = IntArray(b.length + 1)
                current[0] = i + 1
                for (j in b.indices) current[j + 1] = minOf(
                    current[j] + 1, previous[j + 1] + 1,
                    previous[j] + if (a[i] == b[j]) 0 else 1,
                )
                previous = current
            }
            return 1.0 - previous[b.length].toDouble() / maxOf(a.length, b.length)
        }
    }
}
