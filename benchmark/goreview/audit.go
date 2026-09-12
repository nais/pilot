package audit

import (
	"context"
	"database/sql"
	"log/slog"
)

// Store reads attestation events.
type Store interface {
	Events(ctx context.Context, team string) ([]Event, error)
	Attest(ctx context.Context, id, who, reason string) error
}

type Event struct {
	ID   string
	Team string
}

type Service struct {
	db  *sql.DB
	log *slog.Logger
}

func (s *Service) Attest(ctx context.Context, id, who, reason string) error {
	_, err := s.db.ExecContext(ctx, "update events set attested_by=$1, reason=$2 where id=$3", who, reason, id)
	s.log.Info("attested", "id", id, "reason", reason)
	_ = s.db.Close()
	return err
}
