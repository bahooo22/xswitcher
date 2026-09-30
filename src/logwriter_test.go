package main

import (
	"os"
	"strings"
	"testing"
)

func captureStderr(t *testing.T, f func()) string {
	t.Helper()
	orig := os.Stderr
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	os.Stderr = w
	f()
	os.Stderr = orig
	w.Close()
	defer r.Close()
	var b strings.Builder
	buf := make([]byte, 4096)
	for {
		n, readErr := r.Read(buf)
		b.Write(buf[:n])
		if readErr != nil {
			return b.String()
		}
	}
}

// A missing /dev/log used to leave SYSLOG nil, and the very first SYSLOG.Warning()
// then crashed main() before any device was opened.
func TestLogWriterWithoutSyslogDoesNotPanic(t *testing.T) {
	l := logWriter{}
	l.Debug("d %d", 1)
	l.Info("i")
	l.Notice("n")
	l.Warning("w")
	l.Err("e")
}

func TestLogWriterStderrFallback(t *testing.T) {
	l := logWriter{stderr: true}
	got := captureStderr(t, func() { l.Warning("breadcrumb") })
	if !strings.Contains(got, "WARNING breadcrumb") {
		t.Fatalf("marker lost from the stderr fallback: %q", got)
	}
}
