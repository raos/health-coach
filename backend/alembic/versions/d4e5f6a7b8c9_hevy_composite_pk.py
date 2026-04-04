"""hevy_composite_pk

Revision ID: d4e5f6a7b8c9
Revises: c3f1a2b4d5e6
Create Date: 2026-04-03 00:00:01.000000

Replace the string-prefix workaround (from c3f1a2b4d5e6) with a proper
composite primary key (id, user_id) on hevy_workouts — matching the pattern
used by strava_activities.

Steps:
  1. Drop the composite FK on hevy_exercise_sets (references the old single-col PK).
  2. Strip the "{user_id}:" prefix from hevy_exercise_sets.workout_id.
  3. Strip the "{user_id}:" prefix from hevy_workouts.id.
  4. Make hevy_workouts.user_id NOT NULL (required for a PK column).
  5. Drop the single-column PK on hevy_workouts.
  6. Add composite PK (id, user_id) on hevy_workouts.
  7. Add composite FK (workout_id, user_id) → hevy_workouts(id, user_id) on hevy_exercise_sets.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3f1a2b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop FK from hevy_exercise_sets so we can freely update workout_id values.
    op.drop_constraint(
        "hevy_exercise_sets_workout_id_fkey",
        "hevy_exercise_sets",
        type_="foreignkey",
    )

    # 2. Strip "{user_id}:" prefix from exercise_sets.workout_id.
    op.execute("""
        UPDATE hevy_exercise_sets
        SET workout_id = SUBSTRING(workout_id FROM POSITION(':' IN workout_id) + 1)
        WHERE POSITION(':' IN workout_id) > 0
    """)

    # 3. Strip "{user_id}:" prefix from workouts.id.
    op.execute("""
        UPDATE hevy_workouts
        SET id = SUBSTRING(id FROM POSITION(':' IN id) + 1)
        WHERE POSITION(':' IN id) > 0
    """)

    # 4. Make user_id NOT NULL (all rows already have a value — verified above).
    op.alter_column("hevy_workouts", "user_id", nullable=False)

    # 5. Drop the existing single-column PK.
    op.drop_constraint("hevy_workouts_pkey", "hevy_workouts", type_="primary")

    # 6. Add composite PK (id, user_id).
    op.create_primary_key("hevy_workouts_pkey", "hevy_workouts", ["id", "user_id"])

    # 7. Add composite FK on hevy_exercise_sets (workout_id, user_id) → hevy_workouts(id, user_id).
    op.create_foreign_key(
        "hevy_exercise_sets_workout_user_fkey",
        "hevy_exercise_sets",
        "hevy_workouts",
        ["workout_id", "user_id"],
        ["id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "hevy_exercise_sets_workout_user_fkey",
        "hevy_exercise_sets",
        type_="foreignkey",
    )

    op.drop_constraint("hevy_workouts_pkey", "hevy_workouts", type_="primary")
    op.create_primary_key("hevy_workouts_pkey", "hevy_workouts", ["id"])
    op.alter_column("hevy_workouts", "user_id", nullable=True)

    # Re-apply "{user_id}:" prefix.
    op.execute("""
        UPDATE hevy_workouts
        SET id = CAST(user_id AS TEXT) || ':' || id
        WHERE user_id IS NOT NULL
    """)
    op.execute("""
        UPDATE hevy_exercise_sets
        SET workout_id = (
            SELECT CAST(w.user_id AS TEXT) || ':' || w.id
            FROM hevy_workouts w
            WHERE w.id = hevy_exercise_sets.workout_id
              AND w.user_id IS NOT NULL
        )
        WHERE EXISTS (
            SELECT 1 FROM hevy_workouts WHERE id = hevy_exercise_sets.workout_id AND user_id IS NOT NULL
        )
    """)

    op.create_foreign_key(
        "hevy_exercise_sets_workout_id_fkey",
        "hevy_exercise_sets",
        "hevy_workouts",
        ["workout_id"],
        ["id"],
    )
