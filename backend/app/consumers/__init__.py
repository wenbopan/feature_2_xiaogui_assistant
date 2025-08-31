#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consumers module for Kafka message processing
"""

from .file_classification_consumer import kafka_consumer_service
from .field_extraction_consumer import field_extraction_consumer
from .file_classification_processor import content_processor
from .field_extraction_processor import field_extraction_processor
from .simple_file_classification_consumer import simple_file_classification_consumer
from .simple_field_extraction_consumer import simple_field_extraction_consumer

__all__ = [
    'kafka_consumer_service',
    'field_extraction_consumer',
    'content_processor',
    'field_extraction_processor',
    'simple_file_classification_consumer',
    'simple_field_extraction_consumer'
]
