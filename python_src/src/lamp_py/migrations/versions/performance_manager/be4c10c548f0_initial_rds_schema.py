"""initial rds schema

Revision ID: be4c10c548f0
Revises: 
Create Date: 2023-03-22 11:34:01.581606

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'be4c10c548f0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('metadata_log',
    sa.Column('pk_id', sa.Integer(), nullable=False),
    sa.Column('processed', sa.Boolean(), nullable=True),
    sa.Column('process_fail', sa.Boolean(), nullable=True),
    sa.Column('path', sa.String(length=256), nullable=False),
    sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('pk_id'),
    sa.UniqueConstraint('path')
    )
    op.create_table('static_calendar',
    sa.Column('pk_id', sa.Integer(), nullable=False),
    sa.Column('service_id', sa.String(length=128), nullable=False),
    sa.Column('monday', sa.Boolean(), nullable=True),
    sa.Column('tuesday', sa.Boolean(), nullable=True),
    sa.Column('wednesday', sa.Boolean(), nullable=True),
    sa.Column('thursday', sa.Boolean(), nullable=True),
    sa.Column('friday', sa.Boolean(), nullable=True),
    sa.Column('saturday', sa.Boolean(), nullable=True),
    sa.Column('sunday', sa.Boolean(), nullable=True),
    sa.Column('start_date', sa.Integer(), nullable=False),
    sa.Column('end_date', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('pk_id')
    )
    op.create_table('static_feed_info',
    sa.Column('pk_id', sa.Integer(), nullable=False),
    sa.Column('feed_start_date', sa.Integer(), nullable=False),
    sa.Column('feed_end_date', sa.Integer(), nullable=False),
    sa.Column('feed_version', sa.String(length=75), nullable=False),
    sa.Column('timestamp', sa.Integer(), nullable=False),
    sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('pk_id'),
    sa.UniqueConstraint('feed_version'),
    sa.UniqueConstraint('timestamp')
    )
    op.create_table('static_routes',
    sa.Column('pk_id', sa.Integer(), nullable=False),
    sa.Column('route_id', sa.String(length=60), nullable=False),
    sa.Column('agency_id', sa.SmallInteger(), nullable=False),
    sa.Column('route_short_name', sa.String(length=60), nullable=True),
    sa.Column('route_long_name', sa.String(length=150), nullable=True),
    sa.Column('route_desc', sa.String(length=40), nullable=True),
    sa.Column('route_type', sa.SmallInteger(), nullable=False),
    sa.Column('route_sort_order', sa.Integer(), nullable=False),
    sa.Column('route_fare_class', sa.String(length=30), nullable=False),
    sa.Column('line_id', sa.String(length=30), nullable=True),
    sa.Column('timestamp', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('pk_id')
    )
    op.create_table('static_stop_times',
    sa.Column('pk_id', sa.Integer(), nullable=False),
    sa.Column('trip_id', sa.String(length=128), nullable=False),
    sa.Column('arrival_time', sa.Integer(), nullable=False),
    sa.Column('departure_time', sa.Integer(), nullable=False),
    sa.Column('stop_id', sa.String(length=30), nullable=False),
    sa.Column('stop_sequence', sa.SmallInteger(), nullable=False),
    sa.Column('timestamp', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('pk_id')
    )
    op.create_table('static_stops',
    sa.Column('pk_id', sa.Integer(), nullable=False),
    sa.Column('stop_id', sa.String(length=128), nullable=False),
    sa.Column('stop_name', sa.String(length=128), nullable=False),
    sa.Column('stop_desc', sa.String(length=256), nullable=True),
    sa.Column('platform_code', sa.String(length=10), nullable=True),
    sa.Column('platform_name', sa.String(length=60), nullable=True),
    sa.Column('parent_station', sa.String(length=30), nullable=True),
    sa.Column('timestamp', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('pk_id')
    )
    op.create_table('static_trips',
    sa.Column('pk_id', sa.Integer(), nullable=False),
    sa.Column('route_id', sa.String(length=60), nullable=False),
    sa.Column('service_id', sa.String(length=60), nullable=False),
    sa.Column('trip_id', sa.String(length=128), nullable=False),
    sa.Column('direction_id', sa.Boolean(), nullable=True),
    sa.Column('timestamp', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('pk_id')
    )
    op.create_table('temp_hash_compare',
    sa.Column('trip_stop_hash', sa.LargeBinary(length=16), nullable=False),
    sa.PrimaryKeyConstraint('trip_stop_hash')
    )
    op.create_table('vehicle_event_metrics',
    sa.Column('trip_stop_hash', sa.LargeBinary(length=16), nullable=False),
    sa.Column('travel_time_seconds', sa.Integer(), nullable=True),
    sa.Column('dwell_time_seconds', sa.Integer(), nullable=True),
    sa.Column('headway_trunk_seconds', sa.Integer(), nullable=True),
    sa.Column('headway_branch_seconds', sa.Integer(), nullable=True),
    sa.Column('updated_on', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('trip_stop_hash')
    )
    op.create_table('vehicle_trips',
    sa.Column('trip_hash', sa.LargeBinary(length=16), nullable=False),
    sa.Column('direction_id', sa.Boolean(), nullable=False),
    sa.Column('route_id', sa.String(length=60), nullable=False),
    sa.Column('trunk_route_id', sa.String(length=60), nullable=False),
    sa.Column('start_date', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.Integer(), nullable=False),
    sa.Column('vehicle_id', sa.String(length=60), nullable=False),
    sa.Column('stop_count', sa.SmallInteger(), nullable=False),
    sa.Column('static_trip_id_guess', sa.String(length=128), nullable=True),
    sa.Column('static_start_time', sa.Integer(), nullable=True),
    sa.Column('static_stop_count', sa.SmallInteger(), nullable=True),
    sa.Column('first_last_station_match', sa.Boolean(), nullable=False),
    sa.Column('updated_on', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('trip_hash')
    )
    op.create_table('vehicle_events',
    sa.Column('pk_id', sa.Integer(), nullable=False),
    sa.Column('direction_id', sa.Boolean(), nullable=False),
    sa.Column('route_id', sa.String(length=60), nullable=False),
    sa.Column('start_date', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.Integer(), nullable=False),
    sa.Column('vehicle_id', sa.String(length=60), nullable=False),
    sa.Column('trip_hash', sa.LargeBinary(length=16), nullable=False),
    sa.Column('stop_sequence', sa.SmallInteger(), nullable=False),
    sa.Column('stop_id', sa.String(length=60), nullable=False),
    sa.Column('parent_station', sa.String(length=60), nullable=False),
    sa.Column('trip_stop_hash', sa.LargeBinary(length=16), nullable=False),
    sa.Column('vp_move_timestamp', sa.Integer(), nullable=True),
    sa.Column('vp_stop_timestamp', sa.Integer(), nullable=True),
    sa.Column('tu_stop_timestamp', sa.Integer(), nullable=True),
    sa.Column('fk_static_timestamp', sa.Integer(), nullable=False),
    sa.Column('updated_on', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['fk_static_timestamp'], ['static_feed_info.timestamp'], ),
    sa.PrimaryKeyConstraint('pk_id')
    )
    op.create_index(op.f('ix_vehicle_events_trip_hash'), 'vehicle_events', ['trip_hash'], unique=False)
    op.create_index(op.f('ix_vehicle_events_trip_stop_hash'), 'vehicle_events', ['trip_stop_hash'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_vehicle_events_trip_stop_hash'), table_name='vehicle_events')
    op.drop_index(op.f('ix_vehicle_events_trip_hash'), table_name='vehicle_events')
    op.drop_table('vehicle_events')
    op.drop_table('vehicle_trips')
    op.drop_table('vehicle_event_metrics')
    op.drop_table('temp_hash_compare')
    op.drop_table('static_trips')
    op.drop_table('static_stops')
    op.drop_table('static_stop_times')
    op.drop_table('static_routes')
    op.drop_table('static_feed_info')
    op.drop_table('static_calendar')
    op.drop_table('metadata_log')
    # ### end Alembic commands ###
