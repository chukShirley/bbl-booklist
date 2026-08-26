package com.bookscout.app

import android.content.Intent
import android.os.Bundle
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class ScannerActivity : ComponentActivity() {
    private val executor = Executors.newSingleThreadExecutor()
    private val finished = AtomicBoolean(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val frame = FrameLayout(this)
        val previewView = PreviewView(this).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }
        val help = TextView(this).apply {
            text = "Point at the ISBN barcode"
            textSize = 18f
            setTextColor(android.graphics.Color.WHITE)
            setBackgroundColor(0x99000000.toInt())
            setPadding(32, 24, 32, 24)
        }
        frame.addView(previewView, FrameLayout.LayoutParams(-1, -1))
        frame.addView(help, FrameLayout.LayoutParams(-1, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            gravity = android.view.Gravity.BOTTOM
            setMargins(24, 24, 24, 64)
        })
        setContentView(frame)
        startCamera(previewView)
    }

    private fun startCamera(view: PreviewView) {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val preview = Preview.Builder().build().also { it.surfaceProvider = view.surfaceProvider }
            val analysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            val scanner = BarcodeScanning.getClient()
            analysis.setAnalyzer(executor) { proxy ->
                val image = proxy.image
                if (image == null || finished.get()) { proxy.close(); return@setAnalyzer }
                scanner.process(InputImage.fromMediaImage(image, proxy.imageInfo.rotationDegrees))
                    .addOnSuccessListener { codes ->
                        val isbn = codes.firstNotNullOfOrNull { barcode ->
                            barcode.rawValue?.let(BookDatabase::normalizeIsbn)?.takeIf {
                                barcode.format == Barcode.FORMAT_EAN_13 && (it.startsWith("978") || it.startsWith("979"))
                            }
                        }
                        if (isbn != null && finished.compareAndSet(false, true)) {
                            setResult(RESULT_OK, Intent().putExtra(RESULT_ISBN, isbn)); finish()
                        }
                    }.addOnCompleteListener { proxy.close() }
            }
            provider.unbindAll()
            provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
        }, ContextCompat.getMainExecutor(this))
    }

    override fun onDestroy() { executor.shutdown(); super.onDestroy() }

    companion object { const val RESULT_ISBN = "isbn" }
}
