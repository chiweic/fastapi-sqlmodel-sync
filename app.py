from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import ConfigDict, EmailStr, HttpUrl, TypeAdapter
from sqlalchemy import JSON, Column, String, TypeDecorator
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select
from typing import Dict, Optional, List

# this adopt solution proposed from https://github.com/fastapi/sqlmodel/discussions/730
class HttpUrlType(TypeDecorator):
    impl = String(2083)
    cache_ok = True
    python_type = HttpUrl

    def process_bind_param(self, value, dialect) -> str:
        return str(value)

    def process_result_value(self, value, dialect) -> HttpUrl:
        return HttpUrl(url=value)

    def process_literal_param(self, value, dialect) -> str:
        return str(value)


class ScheduleBase(SQLModel):
    model_config = ConfigDict(extra='forbid')

    url:HttpUrl=Field(sa_type=HttpUrlType)
    title: str
    venue: str
    venue_url: Optional[HttpUrl]=Field(default=None, sa_type=HttpUrlType)
    schedule_datetime: str
    locations: Dict = Field(default_factory=dict, sa_column=Column(JSON))
    registration: Optional[Dict] = Field(default_factory=dict, sa_column=Column(JSON))
    description: Optional[str]=Field(default=None)
    

class Schedule(ScheduleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    sections: List['Section'] = Relationship(back_populates="schedule")


class ScheduleCreate(ScheduleBase):
    pass


class SchedulePublic(ScheduleBase):
    id: int


class ScheduleUpdate(ScheduleBase):

    url:HttpUrl | None = None
    title:str | None = None
    venue:str | None = None
    venue_url: Optional[HttpUrl] | None = None
    schedule_datetime: str | None = None
    locations: Dict | None = None
    registration: Dict | None = None
    description: Optional[str] | None = None
    

class SectionBase(SQLModel):
    model_config = ConfigDict(extra='forbid')

    title: str = Field(index=True)
    sequence: str
    status: Optional[str]
    

class Section(SectionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    events: List["Event"] = Relationship(back_populates="section")
    schedule: Schedule | None = Relationship(back_populates="sections")

    schedule_id: int | None = Field(default=None, foreign_key="schedule.id")


class SectionCreate(SectionBase):
    pass


class SectionPublic(SectionBase):
    id: int


class SectionUpdate(SQLModel):
    id: int | None = None
    title: str | None = None
    sequence: str | None = None
    status: str | None = None


import datetime
class EventBase(SQLModel):
    model_config = ConfigDict(extra='forbid')

    start_time: datetime.time
    end_time: datetime.time
    event_date: datetime.date
    location: str

    
    section_id: int | None = Field(default=None, foreign_key="section.id")


class Event(EventBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    section: Section | None = Relationship(back_populates="events")


class EventPublic(EventBase):
    id: int


class EventCreate(EventBase):
    pass


class EventUpdate(SQLModel):
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    event_date: datetime.date | None = None
    location: str | None = None


class EventPublicWithSection(EventPublic):
    section: SectionPublic | None = None


class SectionPublicWithEventes(SectionPublic):
    eventes: List[EventPublic] = []


class SchedulePublicWithSections(SchedulePublic):
    sections: List[SectionPublic] = []


class VenueBase(SQLModel):

    name: str
    Tel: Optional[str] = Field(default=None)
    Address: Optional[str] = Field(default=None)
    Mail: Optional[EmailStr] = Field(default=None)
    url: Optional[HttpUrl] = Field(default=None, sa_type=HttpUrlType)
    Fax: Optional[str] = Field(default=None)
    Contact: Optional[str] = Field(default=None)

    # Tel or Fax must start with + or digit
    # TODO on V.2

class VenuePublic(VenueBase):
    id: int


class VenueCreate(VenueBase):
    pass


class Venue(VenueBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class VenueUpdate(VenueBase):
    name: str | None = None
    Tel: Optional[str]  | None = None
    Address: Optional[str]  | None = None
    Mail: Optional[EmailStr]  | None = None
    url: Optional[HttpUrl]  | None = None
    Fax: Optional[str]  | None = None
    Contact: Optional[str]  | None = None



sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"


connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.post("/events/", response_model=EventPublic)
def create_event(*, session: Session = Depends(get_session), event: EventCreate):
    db_event = Event.model_validate(event)
    session.add(db_event)
    session.commit()
    session.refresh(db_event)
    return db_event


@app.get("/events/", response_model=list[EventPublic])
def read_events(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    eventes = session.exec(select(Event).offset(offset).limit(limit)).all()
    return eventes


@app.get("/events/{event_id}", response_model=EventPublicWithSection)
def read_event(*, session: Session = Depends(get_session), event_id: int):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.patch("/events/{event_id}", response_model=EventPublic)
def update_event(
    *, session: Session = Depends(get_session), event_id: int, event: EventUpdate
):
    db_event = session.get(Event, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    event_data = event.model_dump(exclude_unset=True)
    for key, value in event_data.items():
        setattr(db_event, key, value)
    session.add(db_event)
    session.commit()
    session.refresh(db_event)
    return db_event


@app.delete("/events/{event_id}")
def delete_event(*, session: Session = Depends(get_session), event_id: int):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    session.delete(event)
    session.commit()
    return {"ok": True}


@app.post("/sections/", response_model=SectionPublic)
def create_section(*, session: Session = Depends(get_session), section: SectionCreate):
    db_section = Section.model_validate(section)
    session.add(db_section)
    session.commit()
    session.refresh(db_section)
    return db_section


@app.get("/sections/", response_model=list[SectionPublic])
def read_sections(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    sections = session.exec(select(Section).offset(offset).limit(limit)).all()
    return sections


@app.get("/sections/{section_id}", response_model=SectionPublicWithEventes)
def read_section(*, section_id: int, session: Session = Depends(get_session)):
    section = session.get(Section, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section


@app.patch("/sections/{section_id}", response_model=SectionPublic)
def update_section(
    *,
    session: Session = Depends(get_session),
    section_id: int,
    section: SectionUpdate,
):
    db_section = session.get(Section, section_id)
    if not db_section:
        raise HTTPException(status_code=404, detail="Section not found")
    section_data = section.model_dump(exclude_unset=True)
    for key, value in section_data.items():
        setattr(db_section, key, value)
    session.add(db_section)
    session.commit()
    session.refresh(db_section)
    return db_section


@app.delete("/sections/{section_id}")
def delete_section(*, session: Session = Depends(get_session), section_id: int):
    section = session.get(Section, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    session.delete(section)
    session.commit()
    return {"ok": True}


@app.post("/schedules/", response_model=SchedulePublic)
def create_schedule(*, session: Session = Depends(get_session), schedule: ScheduleCreate):
    db_schedule = Schedule.model_validate(schedule)
    session.add(db_schedule)
    session.commit()
    session.refresh(db_schedule)
    return db_schedule


@app.get("/schedules/", response_model=list[SchedulePublic])
def read_schedules(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    schedules = session.exec(select(Schedule).offset(offset).limit(limit)).all()
    return schedules


@app.get("/schedules/{schedule_id}", response_model=SchedulePublicWithSections)
def read_schedule(*, schedule_id: int, session: Session = Depends(get_session)):
    schedule = session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@app.patch("/schedules/{schedule_id}", response_model=SchedulePublic)
def update_schedule(
    *,
    session: Session = Depends(get_session),
    schedule_id: int,
    schedule: ScheduleUpdate,
):
    db_schedule = session.get(Schedule, schedule_id)
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule_data = schedule.model_dump(exclude_unset=True)
    for key, value in schedule_data.items():
        setattr(db_schedule, key, value)
    session.add(db_schedule)
    session.commit()
    session.refresh(db_schedule)
    return db_schedule


@app.delete("/schedules/{schedule_id}")
def delete_schedule(*, session: Session = Depends(get_session), schedule_id: int):
    schedule = session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    session.delete(schedule)
    session.commit()
    return {"ok": True}


@app.post("/venues/", response_model=VenuePublic)
def create_venue(*, session: Session = Depends(get_session), venue: VenueCreate):
    db_venue = Venue.model_validate(venue)
    session.add(db_venue)
    session.commit()
    session.refresh(db_venue)
    return db_venue


@app.get("/venues/", response_model=list[VenuePublic])
def read_venues(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    venuees = session.exec(select(Venue).offset(offset).limit(limit)).all()
    return venuees


@app.get("/venues/{venue_id}", response_model=VenuePublic)
def read_venue(*, session: Session = Depends(get_session), venue_id: int):
    venue = session.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


@app.patch("/venues/{venue_id}", response_model=VenuePublic)
def update_venue(
    *, session: Session = Depends(get_session), venue_id: int, venue: VenueUpdate
):
    db_venue = session.get(Venue, venue_id)
    if not db_venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    venue_data = venue.model_dump(exclude_unset=True)
    for key, value in venue_data.items():
        setattr(db_venue, key, value)
    session.add(db_venue)
    session.commit()
    session.refresh(db_venue)
    return db_venue


@app.delete("/venues/{venue_id}")
def delete_venue(*, session: Session = Depends(get_session), venue_id: int):
    venue = session.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    session.delete(venue)
    session.commit()
    return {"ok": True}