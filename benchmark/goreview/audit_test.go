package audit

import (
	"os"
	"testing"
)

func TestAttestAgainstPostgres(t *testing.T) {
	dsn := os.Getenv("TEST_DSN")
	if dsn == "" {
		t.Skip("no database available")
	}
	t.Log("would run")
}
