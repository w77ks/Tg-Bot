     
        # Запускаем бота
        logging.info("Бот запущен...")
        print("Бот успешно запущен! Нажмите Ctrl+C для остановки.")
        app.run_polling()
        
    except Exception as e:
        logging.error(f"Ошибка запуска бота: {e}")
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()

