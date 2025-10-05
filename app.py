#!/usr/bin/env python3
"""
Conversation Quality Rating & Analytics System
A FastAPI backend for collecting and analyzing conversation ratings
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from enum import Enum
import sqlite3
import json
import io
import pandas as pd

# Initialize FastAPI app
app = FastAPI(
    title="Conversation Rating System",
    description="API for collecting and analyzing conversation quality ratings",
    version="1.0.0"
)


# Data Models
class RatingCreate(BaseModel):
    """Model for creating a new rating"""
    conversation_id: str = Field(..., description="Unique conversation identifier")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    feedback: Optional[str] = Field(None, description="Optional text feedback")
    user_id: Optional[str] = Field(None, description="User who submitted rating")
    metadata: Optional[Dict] = Field(default_factory=dict, description="Additional context")


class Rating(RatingCreate):
    """Model for a stored rating with system fields"""
    id: int
    timestamp: str
    sentiment: str


class SentimentType(str, Enum):
    """Sentiment categories"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


# Database Management
class Database:
    """SQLite database manager"""
    
    def __init__(self, db_path: str = "ratings.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                feedback TEXT,
                user_id TEXT,
                metadata TEXT,
                timestamp TEXT NOT NULL,
                sentiment TEXT NOT NULL
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON ratings(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rating ON ratings(rating)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation ON ratings(conversation_id)
        """)
        
        conn.commit()
        conn.close()
        
        print("✓ Database initialized successfully")
    
    def insert_rating(self, rating_data: RatingCreate) -> Dict:
        """Insert a new rating"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        sentiment = self._calculate_sentiment(rating_data.rating, rating_data.feedback)
        metadata_json = json.dumps(rating_data.metadata)
        
        cursor.execute("""
            INSERT INTO ratings (conversation_id, rating, feedback, user_id, metadata, timestamp, sentiment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            rating_data.conversation_id,
            rating_data.rating,
            rating_data.feedback,
            rating_data.user_id,
            metadata_json,
            timestamp,
            sentiment
        ))
        
        rating_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "id": rating_id,
            "conversation_id": rating_data.conversation_id,
            "rating": rating_data.rating,
            "feedback": rating_data.feedback,
            "user_id": rating_data.user_id,
            "metadata": rating_data.metadata,
            "timestamp": timestamp,
            "sentiment": sentiment
        }
    
    def get_ratings(self, limit: int = 100, min_rating: Optional[int] = None,
                    max_rating: Optional[int] = None) -> List[Dict]:
        """Get ratings with optional filters"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM ratings WHERE 1=1"
        params = []
        
        if min_rating:
            query += " AND rating >= ?"
            params.append(min_rating)
        
        if max_rating:
            query += " AND rating <= ?"
            params.append(max_rating)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        ratings = []
        for row in rows:
            rating = dict(row)
            rating['metadata'] = json.loads(rating['metadata']) if rating['metadata'] else {}
            ratings.append(rating)
        
        return ratings
    
    def get_rating_by_id(self, rating_id: int) -> Optional[Dict]:
        """Get a specific rating by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM ratings WHERE id = ?", (rating_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            rating = dict(row)
            rating['metadata'] = json.loads(rating['metadata']) if rating['metadata'] else {}
            return rating
        return None
    
    def delete_rating(self, rating_id: int) -> bool:
        """Delete a rating"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM ratings WHERE id = ?", (rating_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def get_all_ratings(self) -> List[Dict]:
        """Get all ratings for export"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM ratings ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()
        
        ratings = []
        for row in rows:
            rating = dict(row)
            rating['metadata'] = json.loads(rating['metadata']) if rating['metadata'] else {}
            ratings.append(rating)
        
        return ratings
    
    @staticmethod
    def _calculate_sentiment(rating: int, feedback: Optional[str]) -> str:
        """Calculate sentiment based on rating"""
        if rating >= 4:
            return SentimentType.POSITIVE.value
        elif rating == 3:
            return SentimentType.NEUTRAL.value
        else:
            return SentimentType.NEGATIVE.value


# Analytics Engine
class Analytics:
    """Analytics and statistics calculator"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_summary(self) -> Dict:
        """Get overall summary statistics"""
        ratings = self.db.get_all_ratings()
        
        if not ratings:
            return {
                "total_ratings": 0,
                "average_rating": 0,
                "rating_distribution": {str(i): 0 for i in range(1, 6)},
                "sentiment_breakdown": {s.value: 0 for s in SentimentType},
                "time_period": "all_time"
            }
        
        # Calculate statistics
        rating_values = [r['rating'] for r in ratings]
        avg_rating = sum(rating_values) / len(rating_values)
        
        # Rating distribution
        distribution = {str(i): 0 for i in range(1, 6)}
        for rating in rating_values:
            distribution[str(rating)] += 1
        
        # Sentiment breakdown
        sentiment_counts = {s.value: 0 for s in SentimentType}
        for rating in ratings:
            sentiment_counts[rating['sentiment']] += 1
        
        return {
            "total_ratings": len(ratings),
            "average_rating": round(avg_rating, 2),
            "rating_distribution": distribution,
            "sentiment_breakdown": sentiment_counts,
            "time_period": "all_time"
        }
    
    def get_distribution(self) -> Dict:
        """Get detailed rating distribution with percentages"""
        ratings = self.db.get_all_ratings()
        total = len(ratings)
        
        if total == 0:
            return {
                "total_ratings": 0,
                "distribution": {}
            }
        
        distribution = {}
        for i in range(1, 6):
            count = sum(1 for r in ratings if r['rating'] == i)
            percentage = (count / total) * 100
            distribution[f"{i}_star"] = {
                "count": count,
                "percentage": round(percentage, 1)
            }
        
        return {
            "total_ratings": total,
            "distribution": distribution
        }
    
    def get_trends(self, days: int = 7) -> Dict:
        """Get rating trends over time"""
        ratings = self.db.get_all_ratings()
        
        # Filter by date range
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_ratings = [
            r for r in ratings
            if datetime.fromisoformat(r['timestamp']) >= cutoff_date
        ]
        
        if not recent_ratings:
            return {
                "period_days": days,
                "total_ratings": 0,
                "average_rating": 0,
                "trend": "no_data"
            }
        
        # Calculate average for period
        avg_rating = sum(r['rating'] for r in recent_ratings) / len(recent_ratings)
        
        # Simple trend calculation (compare first half vs second half)
        mid_point = len(recent_ratings) // 2
        if mid_point > 0:
            first_half_avg = sum(r['rating'] for r in recent_ratings[:mid_point]) / mid_point
            second_half_avg = sum(r['rating'] for r in recent_ratings[mid_point:]) / (len(recent_ratings) - mid_point)
            
            if second_half_avg > first_half_avg + 0.2:
                trend = "improving"
            elif second_half_avg < first_half_avg - 0.2:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "period_days": days,
            "total_ratings": len(recent_ratings),
            "average_rating": round(avg_rating, 2),
            "trend": trend
        }
    
    def get_sentiment_analysis(self) -> Dict:
        """Get detailed sentiment analysis"""
        ratings = self.db.get_all_ratings()
        
        if not ratings:
            return {
                "total_ratings": 0,
                "sentiment_breakdown": {},
                "top_positive_feedback": [],
                "top_negative_feedback": []
            }
        
        # Sentiment counts
        sentiment_counts = {s.value: 0 for s in SentimentType}
        for rating in ratings:
            sentiment_counts[rating['sentiment']] += 1
        
        # Get feedback samples
        positive_feedback = [r['feedback'] for r in ratings if r['sentiment'] == 'positive' and r['feedback']]
        negative_feedback = [r['feedback'] for r in ratings if r['sentiment'] == 'negative' and r['feedback']]
        
        return {
            "total_ratings": len(ratings),
            "sentiment_breakdown": sentiment_counts,
            "top_positive_feedback": positive_feedback[:5],
            "top_negative_feedback": negative_feedback[:5]
        }


# Initialize database and analytics
db = Database()
analytics = Analytics(db)


# API Endpoints

@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "name": "Conversation Rating System API",
        "version": "1.0.0",
        "description": "API for collecting and analyzing conversation ratings",
        "docs": "/docs",
        "endpoints": {
            "ratings": "/ratings",
            "analytics": "/analytics/summary",
            "export": "/export"
        }
    }


@app.post("/ratings", response_model=Dict, status_code=201)
def create_rating(rating: RatingCreate):
    """
    Submit a new conversation rating
    
    - **conversation_id**: Unique identifier for the conversation
    - **rating**: Rating from 1 to 5 stars
    - **feedback**: Optional text feedback
    - **user_id**: Optional user identifier
    - **metadata**: Optional additional context (JSON object)
    """
    try:
        result = db.insert_rating(rating)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating rating: {str(e)}")


@app.get("/ratings")
def get_ratings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of ratings to return"),
    min_rating: Optional[int] = Query(None, ge=1, le=5, description="Minimum rating filter"),
    max_rating: Optional[int] = Query(None, ge=1, le=5, description="Maximum rating filter")
):
    """
    Get ratings with optional filters
    
    - **limit**: Maximum number of ratings to return (default: 100)
    - **min_rating**: Filter by minimum rating (1-5)
    - **max_rating**: Filter by maximum rating (1-5)
    """
    try:
        ratings = db.get_ratings(limit=limit, min_rating=min_rating, max_rating=max_rating)
        return {
            "count": len(ratings),
            "ratings": ratings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching ratings: {str(e)}")


@app.get("/ratings/{rating_id}")
def get_rating(rating_id: int):
    """Get a specific rating by ID"""
    rating = db.get_rating_by_id(rating_id)
    if not rating:
        raise HTTPException(status_code=404, detail=f"Rating {rating_id} not found")
    return rating


@app.delete("/ratings/{rating_id}")
def delete_rating(rating_id: int):
    """Delete a rating"""
    success = db.delete_rating(rating_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Rating {rating_id} not found")
    return {"message": f"Rating {rating_id} deleted successfully"}


@app.get("/analytics/summary")
def get_analytics_summary():
    """
    Get overall analytics summary
    
    Returns:
    - Total ratings
    - Average rating
    - Rating distribution (1-5 stars)
    - Sentiment breakdown
    """
    return analytics.get_summary()


@app.get("/analytics/distribution")
def get_analytics_distribution():
    """
    Get detailed rating distribution with percentages
    """
    return analytics.get_distribution()


@app.get("/analytics/trends")
def get_analytics_trends(days: int = Query(7, ge=1, le=365, description="Number of days to analyze")):
    """
    Get rating trends over time
    
    - **days**: Number of days to analyze (default: 7)
    """
    return analytics.get_trends(days=days)


@app.get("/analytics/sentiment")
def get_sentiment_analysis():
    """
    Get detailed sentiment analysis with feedback samples
    """
    return analytics.get_sentiment_analysis()


@app.get("/export")
def export_data(format: str = Query("json", regex="^(json|csv)$", description="Export format: json or csv")):
    """
    Export all ratings data
    
    - **format**: Export format - 'json' or 'csv' (default: json)
    """
    try:
        ratings = db.get_all_ratings()
        
        if format == "json":
            return JSONResponse(content={"ratings": ratings})
        
        elif format == "csv":
            # Convert to DataFrame and then CSV
            df = pd.DataFrame(ratings)
            
            # Convert metadata dict to string for CSV
            if 'metadata' in df.columns:
                df['metadata'] = df['metadata'].apply(json.dumps)
            
            # Create CSV in memory
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            
            return StreamingResponse(
                iter([csv_buffer.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=ratings.csv"}
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting data: {str(e)}")


@app.post("/import")
def import_ratings(ratings: List[RatingCreate]):
    """
    Bulk import ratings
    
    Accepts a list of rating objects for batch import
    """
    try:
        results = []
        for rating in ratings:
            result = db.insert_rating(rating)
            results.append(result)
        
        return {
            "message": f"Successfully imported {len(results)} ratings",
            "imported_count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing ratings: {str(e)}")


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# Run the application
if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("🚀 Starting Conversation Rating System API")
    print("="*60)
    print(f"📍 API URL: http://localhost:8000")
    print(f"📚 Interactive docs: http://localhost:8000/docs")
    print(f"📖 Alternative docs: http://localhost:8000/redoc")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
