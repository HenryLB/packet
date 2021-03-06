"""
Defines the application's database models.
"""

from datetime import datetime
from functools import lru_cache

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

from . import db

# The required number of off-floor and alumni signatures
REQUIRED_MISC_SIGNATURES = 15


class Freshman(db.Model):
    __tablename__ = "freshman"
    rit_username = Column(String(10), primary_key=True)
    name = Column(String(64), nullable=False)
    onfloor = Column(Boolean, nullable=False)
    fresh_signatures = relationship("FreshSignature")

    # One freshman can have multiple packets if they repeat the intro process
    packets = relationship("Packet", order_by="desc(Packet.id)")

    def current_packet(self):
        """
        :return: The most recent packet for this freshman
        """
        return next(iter(self.packets), None)


class Packet(db.Model):
    __tablename__ = "packet"
    id = Column(Integer, primary_key=True, autoincrement=True)
    freshman_username = Column(ForeignKey("freshman.rit_username"))
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=False)
    info_eboard = Column(Text, nullable=True)   # Used to fulfil the eboard description requirement
    info_events = Column(Text, nullable=True)   # Used to fulfil the events list requirement
    info_achieve = Column(Text, nullable=True)  # Used to fulfil the technical achievements list requirement

    freshman = relationship("Freshman", back_populates="packets")
    upper_signatures = relationship("UpperSignature")
    fresh_signatures = relationship("FreshSignature")
    misc_signatures = relationship("MiscSignature")

    def is_open(self):
        return self.start < datetime.now() < self.end

    @lru_cache(maxsize=1024)
    def signatures_required(self, total=False):
        if total:
            return len(self.upper_signatures) + len(self.fresh_signatures) + REQUIRED_MISC_SIGNATURES
        eboard = UpperSignature.query.with_parent(self).filter_by(eboard=True).count()
        return {'eboard': eboard,
                'upperclassmen': len(self.upper_signatures) - eboard,
                'freshmen': len(self.fresh_signatures),
                'miscellaneous': REQUIRED_MISC_SIGNATURES}

    def signatures_received(self, total=False):
        """
        Result capped so it will never be greater than that of signatures_required()
        """
        misc_count = len(self.misc_signatures)

        if misc_count > REQUIRED_MISC_SIGNATURES:
            misc_count = REQUIRED_MISC_SIGNATURES

        eboard_count = db.session.query(UpperSignature.member) \
            .select_from(Packet).join(UpperSignature) \
            .filter(Packet.freshman_username == self.freshman_username,
                    UpperSignature.signed, UpperSignature.eboard) \
            .distinct().count()

        upper_count = db.session.query(UpperSignature.member) \
            .select_from(Packet).join(UpperSignature) \
            .filter(Packet.freshman_username == self.freshman_username,
                    UpperSignature.signed,
                    UpperSignature.eboard.isnot(True)) \
            .distinct().count()

        fresh_count = db.session.query(FreshSignature.freshman_username) \
            .select_from(Packet).join(FreshSignature) \
            .filter(Packet.freshman_username == self.freshman_username,
                    FreshSignature.signed) \
            .distinct().count()

        if total:
            return eboard_count + upper_count + fresh_count + misc_count

        return {'eboard': eboard_count,
                'upperclassmen': upper_count,
                'freshmen': fresh_count,
                'miscellaneous': misc_count}


class UpperSignature(db.Model):
    __tablename__ = "signature_upper"
    packet_id = Column(Integer, ForeignKey("packet.id"), primary_key=True)
    member = Column(String(36), primary_key=True)
    signed = Column(Boolean, default=False, nullable=False)
    eboard = Column(Boolean, default=False, nullable=False)
    updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    packet = relationship("Packet", back_populates="upper_signatures")


class FreshSignature(db.Model):
    __tablename__ = "signature_fresh"
    packet_id = Column(Integer, ForeignKey("packet.id"), primary_key=True)
    freshman_username = Column(ForeignKey("freshman.rit_username"), primary_key=True)
    signed = Column(Boolean, default=False, nullable=False)
    updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    packet = relationship("Packet", back_populates="fresh_signatures")
    freshman = relationship("Freshman", back_populates="fresh_signatures")


class MiscSignature(db.Model):
    __tablename__ = "signature_misc"
    packet_id = Column(Integer, ForeignKey("packet.id"), primary_key=True)
    member = Column(String(36), primary_key=True)
    updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    packet = relationship("Packet", back_populates="misc_signatures")
