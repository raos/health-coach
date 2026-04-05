"""namespace_hevy_workout_ids

Revision ID: c3f1a2b4d5e6
Revises: b7a963e4dad0
Create Date: 2026-04-03 00:00:00.000000

Migrate hevy_workouts.id from plain Hevy UUID to "{user_id}:{hevy_uuid}" so that
two users sharing the same Hevy API key can each store their own copy of every
workout without hitting a primary-key conflict.

Steps (order matters because of the FK from hevy_exercise_sets.workout_id):
  1. Update hevy_exercise_sets.workout_id to the namespaced form.
  2. Update hevy_workouts.id to the namespaced form.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3f1a2b4d5e6'
down_revision: Union[str, None] = 'b7a963e4dad0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the FK so PostgreSQL doesn't reject the intermediate state where
    # exercise_sets.workout_id already has the new namespaced value but
    # hevy_workouts.id hasn't been updated yet.
    op.drop_constraint(
        "hevy_exercise_sets_workout_id_fkey",
        "hevy_exercise_sets",
        type_="foreignkey",
    )

    # Step 1: update exercise_sets.workout_id to the namespaced form.
    op.execute("""
        UPDATE hevy_exercise_sets
        SET workout_id = (
            SELECT CAST(w.user_id AS TEXT) || ':' || w.id
            FROM hevy_workouts w
            WHERE w.id = hevy_exercise_sets.workout_id
              AND w.user_id IS NOT NULL
        )
        WHERE EXISTS (
            SELECT 1 FROM hevy_workouts
            WHERE id = hevy_exercise_sets.workout_id
              AND user_id IS NOT NULL
        )
    """)

    # Step 2: namespace the workout PKs themselves.
    op.execute("""
        UPDATE hevy_workouts
        SET id = CAST(user_id AS TEXT) || ':' || id
        WHERE user_id IS NOT NULL
    """)

    # Restore the FK.
    op.create_foreign_key(
        "hevy_exercise_sets_workout_id_fkey",
        "hevy_exercise_sets",
        "hevy_workouts",
        ["workout_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "hevy_exercise_sets_workout_id_fkey",
        "hevy_exercise_sets",
        type_="foreignkey",
    )

    # Strip the "{user_id}:" prefix — use position of first colon.
    op.execute("""
        UPDATE hevy_workouts
        SET id = SUBSTRING(id FROM POSITION(':' IN id) + 1)
        WHERE user_id IS NOT NULL
          AND POSITION(':' IN id) > 0
    """)

    op.execute("""
        UPDATE hevy_exercise_sets
        SET workout_id = SUBSTRING(workout_id FROM POSITION(':' IN workout_id) + 1)
        WHERE POSITION(':' IN workout_id) > 0
    """)

    op.create_foreign_key(
        "hevy_exercise_sets_workout_id_fkey",
        "hevy_exercise_sets",
        "hevy_workouts",
        ["workout_id"],
        ["id"],
    )
